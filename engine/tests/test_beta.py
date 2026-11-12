"""Coleta do beta e métricas do piloto (T20): tudo calculado do banco local."""

from __future__ import annotations

import json
import socket
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.application.beta import batch_metrics, beta_report
from qa_engine.application.contracts import validate
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def orientation(angle: int, decided: str | None, **params: Any) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "id": f"o-{angle}-{decided}-{len(params)}",
        "rule": "orientation",
        "target": {"kind": "page", "id": "p"},
        "confidence": 0.95,
        "correction": {"action": "rotate", "params": {"angle_deg": angle, **params}},
    }
    if decided:
        finding["decision"] = {
            "action": decided,
            "reviewer": "g",
            "decided_at": "2026-12-01T10:00:00+00:00",
        }
    return finding


def other(rule: str, decided: str | None) -> dict[str, Any]:
    finding: dict[str, Any] = {
        "id": f"{rule}-{decided}",
        "rule": rule,
        "target": {"kind": "page", "id": "p"},
        "correction": {"action": "none", "params": {}},
    }
    if decided:
        finding["decision"] = {
            "action": decided,
            "reviewer": "g",
            "decided_at": "2026-12-01T10:05:00+00:00",
        }
    return finding


def test_batch_metrics_and_report() -> None:
    report = {
        "batch": {
            "analyzed_at": "2026-12-01T09:01:00+00:00",
            "summary": {"pages_total": 10, "pages_without_review": 7},
        },
        "pages": [{"id": f"p{i}", "numbering": {"state": "read"}} for i in range(8)]
        + [{"id": "p8"}, {"id": "p9"}],
        "findings": [
            orientation(90, "correct"),  # mantida
            orientation(180, "approve"),  # desfeita (falso positivo)
            orientation(
                270, "correct", manual=True, model_angle_deg=90, model_review=False
            ),  # outro ângulo, era automática
            orientation(90, "correct", manual=True),  # o garantidor achou sozinho
            orientation(90, None, review=True),  # ainda pendente
            other("blur", "reject"),
            other("blur", "approve"),
            other("skew", "correct"),
        ],
    }
    overrides = [
        {
            "page_id": "p1",
            "value": "2",
            "decided_at": "2026-12-01T10:10:00+00:00",
            "model_value": "2",
            "model_state": "inferred",
        },
        {
            "page_id": "p2",
            "value": "3",
            "decided_at": "2026-12-01T10:12:00+00:00",
            "model_value": "8",
            "model_state": "read",
        },
        {
            "page_id": "p3",
            "value": "4",
            "decided_at": "2026-12-01T10:14:00+00:00",
            "model_value": None,
            "model_state": "ambiguous",
        },
    ]
    batch = {"id": "b1", "name": "Caixa 1", "created_at": "2026-12-01T09:00:00+00:00"}
    m = batch_metrics(batch, report, [{"decided_at": "2026-12-01T10:00:00+00:00"}], overrides, [])
    assert m["orientation"] == {
        "model_decided": 3,
        "kept": 1,
        "changed_angle": 1,
        "reverted": 1,
        "auto_reverted": 2,
        "found_by_reviewer": 1,
    }
    assert m["rules"]["orientation"] == {"alerts": 4, "real": 2, "false_positive": 1, "pending": 1}
    assert m["numbering"] == {"pages": 8, "typed": 3, "typed_agreed": 1, "missed": 1}
    assert m["analysis_seconds"] == 60 and m["review_seconds"] == 14 * 60

    old = {**m, "batch_id": "b0", "created_at": "2026-11-01T09:00:00+00:00"}
    r = beta_report([m, old], {"numbering": 3, "orientation": 2}, since="2026-11-15")
    validate(r, "beta-report.schema.json")
    assert r["batches"] == 1  # o lote de novembro fica fora do período
    assert r["defects"]["real"] == 4 and r["defects"]["false_positive"] == 2
    assert r["defects"]["found_only_by_reviewer"] == 2  # giro achado sozinho + número lido errado
    assert r["numbering"]["matched"] == 6 and r["numbering"]["typed_ratio"] == pytest.approx(
        3 / 8, abs=1e-4
    )
    assert r["pages"]["without_review_ratio"] == 0.7
    assert r["originals"] == {"batches_checked": 1, "batches_changed": 0, "files_changed": 0}


@pytest.fixture
def client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data.update({"id": "test", "resolution": {"min_dpi": 150}})
    data["feedback"] = {"enabled": True, "retention_days": 30}
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def analyzed(client: TestClient, batch: Path) -> dict[str, Any]:
    files = [
        ("files", (f"lote/{p.relative_to(batch).as_posix()}", p.read_bytes(), "image/tiff"))
        for p in sorted(batch.rglob("*.tif"))
    ]
    batch_id = client.post(
        "/batches", files=files, data={"profile_id": "test"}, headers=AUTH
    ).json()["id"]
    for _ in range(200):
        if client.get(f"/batches/{batch_id}", headers=AUTH).json()["status"] == "analyzed":
            break
        time.sleep(0.1)
    report: dict[str, Any] = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    return report


def test_confirmations_become_local_examples_and_the_report_reads_them(
    client: TestClient, small_batch: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = analyzed(client, small_batch)
    batch_id = report["batch"]["id"]
    doc = report["documents"][1]
    a, b, _ = doc["page_ids"]
    r = client.put(
        f"/batches/{batch_id}/documents/{doc['id']}/numbering",
        json={"reviewer": "g1", "values": {a: "1", b: "2"}},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    client.put(
        f"/batches/{batch_id}/documents/{doc['id']}/numbering",
        json={"reviewer": "g1", "values": {b: None}},
        headers=AUTH,
    )
    page = report["documents"][0]["page_ids"][0]
    r = client.put(
        f"/pages/{page}/rotation", json={"angle_deg": 90, "reviewer": "g1"}, headers=AUTH
    )
    assert r.status_code == 200, r.text

    data_dir = tmp_path / "data"
    repo = SqliteRepository(data_dir / "qa.sqlite3")
    rows = repo.feedback_rows()
    repo.close()
    assert [(row["kind"], row["page_id"]) for row in rows] == [
        ("numbering", a),
        ("orientation", page),
    ]
    numbering_row, orientation_row = rows
    assert numbering_row["label"] == {"text": "1"} and numbering_row["model"]["state"]
    assert (
        orientation_row["label"] == {"angle_deg": 90}
        and orientation_row["model"]["angle_deg"] is None
    )
    assert (data_dir / "feedback" / orientation_row["image_file"]).is_file()

    # Os comandos não usam a rede: qualquer conexão falha o teste.
    def no_network(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("tentou usar a rede")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    out = tmp_path / "beta.json"
    assert cli(["beta", "report", "--data-dir", str(data_dir), "--json", "--out", str(out)]) == 0
    beta = json.loads(out.read_text("utf-8"))
    validate(beta, "beta-report.schema.json")
    assert beta["batches"] == 1 and beta["numbering"]["typed"] == 1
    assert beta["orientation"]["found_by_reviewer"] == 1
    assert beta["feedback"] == {"numbering": 1, "orientation": 1}
    assert cli(["beta", "report", "--data-dir", str(data_dir)]) == 0

    package = tmp_path / "coleta.zip"
    assert cli(["feedback", "export", "--data-dir", str(data_dir), "--out", str(package)]) == 0
    with zipfile.ZipFile(package) as z:
        names = set(z.namelist())
        numbering = json.loads(z.read("numeracao/labels.json"))
        orientation_labels = json.loads(z.read("orientacao/labels.json"))
    assert "LEIA-ME.txt" in names
    assert (
        numbering[0]["text"] == "1" and numbering[0]["file"] is None
    )  # numeração do arquivo: sem recorte
    assert (
        orientation_labels[0]["angle_deg"] == 90
        and f"orientacao/{orientation_labels[0]['file']}" in names
    )


def test_metrics_survive_retention_and_examples_expire(tmp_path: Path) -> None:
    repo = SqliteRepository(tmp_path / "qa.sqlite3")
    repo.save_beta_metrics("b1", "2026-01-01T00:00:00+00:00", {"pages_total": 3})
    assert repo.beta_metrics()["b1"]["pages_total"] == 3
    repo.put_feedback(
        {
            "id": "x",
            "kind": "numbering",
            "batch_id": "b1",
            "page_id": "p1",
            "reviewer": "g",
            "created_at": "2026-01-01T00:00:00+00:00",
            "expires_at": "2026-02-01T00:00:00+00:00",
            "label": {"text": "1"},
            "model": {},
        }
    )
    assert repo.purge_feedback("2026-01-15T00:00:00+00:00") == []
    assert repo.purge_feedback("2026-02-02T00:00:00+00:00") == [None]
    assert repo.feedback_rows() == []
    repo.close()


def test_without_database_the_report_says_so(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert cli(["beta", "report", "--data-dir", str(tmp_path)]) == 1
    assert "nenhum lote" in capsys.readouterr().err
