import io
import json
import time
import zipfile
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.application.contracts import validate
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client(tmp_path: Path, demo_profile_path: Path) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(demo_profile_path.read_text("utf-8"))
    data["id"] = "test"
    data["resolution"] = {"min_dpi": 150}
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=("https://ui.example",),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def upload(client: TestClient, batch: Path) -> dict:  # type: ignore[type-arg]
    files = [
        ("files", (f"lote/{p.relative_to(batch).as_posix()}", p.read_bytes(), "image/tiff"))
        for p in sorted(batch.rglob("*.tif"))
    ]
    marks = {"CX1/DOC1/0001.tif#0": [{"readings": [{"text": "1", "confidence": 0.95}]}]}
    numbering = ("numbering", ("n.json", json.dumps({"pages": marks}), "application/json"))
    r = client.post(
        "/batches", files=[*files, numbering], data={"profile_id": "test"}, headers=AUTH
    )
    assert r.status_code == 202, r.text
    validate(r.json(), "batch-status.schema.json")
    return r.json()


def wait(client: TestClient, batch_id: str) -> dict:  # type: ignore[type-arg]
    for _ in range(200):
        status = client.get(f"/batches/{batch_id}", headers=AUTH).json()
        if status["status"] in {"analyzed", "failed"}:
            return status
        time.sleep(0.1)
    raise AssertionError("análise não terminou")


def test_requires_token(client: TestClient) -> None:
    assert client.get("/health").status_code == 200
    r = client.get("/batches")
    assert r.status_code == 401
    assert r.headers["content-type"].startswith("application/problem+json")


def test_full_review_flow(client: TestClient, small_batch: Path) -> None:
    batch_id = upload(client, small_batch)["id"]
    status = wait(client, batch_id)
    assert status["status"] == "analyzed", status
    validate(status, "batch-status.schema.json")
    assert status["name"] == "lote"

    report = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    validate(report, "analysis.schema.json")
    criticals = client.get(
        f"/batches/{batch_id}/findings", params={"severity": "critical"}, headers=AUTH
    ).json()
    assert criticals and all(f["severity"] == "critical" for f in criticals)

    skew = next(f for f in report["findings"] if f["rule"] == "skew")
    r = client.post(
        f"/findings/{skew['id']}/decision",
        json={"action": "correct", "reviewer": "garantidor1"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    validate(body["finding"], "finding.schema.json")
    assert body["finding"]["decision"]["action"] == "correct"
    assert "skew" not in body["applied"]["remaining_rules"]
    img = client.get(
        f"/pages/{skew['target']['id']}/image",
        params={"variant": "corrected", "max_width": 200},
        headers=AUTH,
    )
    assert img.status_code == 200 and img.headers["content-type"] == "image/png"

    undo = client.delete(f"/findings/{skew['id']}/decision", headers=AUTH)
    assert undo.status_code == 200
    assert "decision" not in undo.json()["finding"]
    again = client.delete(f"/findings/{skew['id']}/decision", headers=AUTH)
    assert again.status_code == 409

    blur = next(f for f in report["findings"] if f["rule"] == "blur")
    r = client.post(
        f"/findings/{blur['id']}/decision",
        json={"action": "source_defect", "reviewer": "garantidor1"},
        headers=AUTH,
    )
    assert r.json()["summary"]["verdict"] in {"rejected", "approved_with_reservations"}
    bad = client.post(f"/findings/{blur['id']}/decision", json={"action": "talvez"}, headers=AUTH)
    assert bad.status_code == 422

    page_id = report["documents"][0]["page_ids"][1]
    r = client.put(
        f"/pages/{page_id}/numbering", json={"value": "2", "reviewer": "g1"}, headers=AUTH
    )
    assert r.status_code == 200, r.text
    assert r.json()["pages"][page_id]["value"] == "2"
    after = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    validate(after, "analysis.schema.json")
    kept = next(f for f in after["findings"] if f["id"] == blur["id"])
    assert kept["decision"]["action"] == "source_defect"

    assert client.post(f"/batches/{batch_id}/exports", headers=AUTH).status_code == 201
    csv = client.get(f"/batches/{batch_id}/exports/rework_order.csv", headers=AUTH)
    assert csv.status_code == 200 and csv.text.startswith("station,box,document")
    doc_id = report["documents"][0]["id"]
    meta = client.get(f"/documents/{doc_id}/metadata", headers=AUTH)
    assert meta.status_code == 200
    put = client.put(
        f"/documents/{doc_id}/metadata/title",
        headers=AUTH,
        json={"value": "Contrato de locação", "reviewer": "g1"},
    )
    assert put.status_code == 200, put.text
    title = next(f for f in put.json() if f["name"] == "title")
    assert title["source"] == "reviewer"
    assert title["confirmed"] is True
    again_meta = client.get(f"/documents/{doc_id}/metadata", headers=AUTH).json()
    assert next(f for f in again_meta if f["name"] == "title")["value"] == "Contrato de locação"
    events = client.get(f"/batches/{batch_id}/events", headers=AUTH)
    assert "event: done" in events.text


def test_zip_upload_and_path_traversal(client: TestClient, small_batch: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for p in small_batch.rglob("*.tif"):
            zf.write(p, f"lote/{p.relative_to(small_batch).as_posix()}")
    r = client.post(
        "/batches",
        files=[("files", ("lote.zip", buf.getvalue(), "application/zip"))],
        data={"profile_id": "test"},
        headers=AUTH,
    )
    assert r.status_code == 202, r.text
    assert wait(client, r.json()["id"])["status"] == "analyzed"

    evil = client.post(
        "/batches",
        files=[("files", ("../../etc/passwd", b"x", "image/png"))],
        data={"profile_id": "test"},
        headers=AUTH,
    )
    assert evil.status_code == 400


def test_profiles(client: TestClient) -> None:
    profiles = client.get("/profiles", headers=AUTH).json()
    assert [p["id"] for p in profiles] == ["test"]
    new = {**profiles[0], "id": "outro"}
    assert client.put("/profiles/outro", json=new, headers=AUTH).status_code == 200
    bad = {**new, "detectors": {"blur": {"params": {"inexistente": 1}}}}
    assert client.put("/profiles/outro", json=bad, headers=AUTH).status_code == 422


def test_repository_is_thread_safe(tmp_path: Path) -> None:
    """Regressão: leituras simultâneas da API quebravam com InterfaceError."""
    from concurrent.futures import ThreadPoolExecutor

    from qa_engine.adapters.sqlite import SqliteRepository

    repo = SqliteRepository(tmp_path / "x.sqlite3")
    repo.create_batch("b", "lote", "demo", tmp_path, "2026-11-05T00:00:00Z")
    with ThreadPoolExecutor(16) as pool:
        results = list(pool.map(lambda _: repo.get_batch("b"), range(2000)))
    assert all(r is not None and r.name == "lote" for r in results)
