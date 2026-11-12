"""Folha que apareceu depois, arrastada para a Sequência (T26)."""

from __future__ import annotations

import hashlib
import io
import random
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "models"
HAS_MODELS = (MODELS / "PP-OCRv5_mobile_det_onnx").is_dir() and (
    MODELS / "PP-OCRv5_mobile_rec_onnx"
).is_dir()
pytestmark = pytest.mark.skipif(not HAS_MODELS, reason="modelos não baixados")
sys.path.insert(0, str(REPO / "tools" / "synth"))

import numbering as handwriting  # noqa: E402
import synth  # noqa: E402

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            h.update(path.relative_to(folder).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def sheet_tiff(folio: str, seed: int = 5) -> bytes:
    gray = handwriting.render_sheet(
        handwriting.Sheet(folio, [handwriting.Written(folio)]), random.Random(seed), 3, 5
    )
    buffer = io.BytesIO()
    Image.fromarray(gray).save(buffer, format="TIFF", compression="tiff_deflate", dpi=(300, 300))
    return buffer.getvalue()


@pytest.fixture
def missing_three(tmp_path: Path) -> Path:
    """Um processo com as folhas 1, 2, 4 e 5 escritas à mão (falta a 3)."""
    root = tmp_path / "Caixa 7"
    rng = random.Random(11)
    for i, folio in enumerate(("1", "2", "4", "5"), start=1):
        gray = handwriting.render_sheet(
            handwriting.Sheet(folio, [handwriting.Written(folio)]), rng, i, 4
        )
        synth.save_tiff(root / f"PROC-1/{i:04d}.tif", synth.Page(gray), synth.STATIONS[0], 1)
    return root


@pytest.fixture
def client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data.update({"id": "test"})
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
        models_dir=MODELS,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def analyzed(client: TestClient, root: Path) -> dict[str, Any]:
    files = [
        ("files", (f"{root.name}/{p.relative_to(root).as_posix()}", p.read_bytes(), "image/tiff"))
        for p in sorted(root.rglob("*.tif"))
    ]
    batch_id = client.post(
        "/batches", files=files, data={"profile_id": "test"}, headers=AUTH
    ).json()["id"]
    for _ in range(600):
        status = client.get(f"/batches/{batch_id}", headers=AUTH).json()
        if status["status"] in {"analyzed", "failed"}:
            break
        time.sleep(0.1)
    assert status["status"] == "analyzed", status
    report: dict[str, Any] = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    return report


def test_found_sheet_closes_the_gap_and_goes_to_the_right_place(
    client: TestClient, missing_three: Path
) -> None:
    before = digest(missing_three)
    report = analyzed(client, missing_three)
    batch_id = report["batch"]["id"]
    doc = report["documents"][0]
    assert any(f["rule"] == "missing_page" for f in report["findings"])

    r = client.post(
        f"/batches/{batch_id}/documents/{doc['id']}/pages",
        files={"file": ("folha-3.tif", sheet_tiff("3"), "image/tiff")},
        data={"reviewer": "g1"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["folio_read"] == "3" and body["suggested_position"] == 3 and body["position"] == 3
    new_id = body["page_id"]
    assert body["document"]["page_ids"][2] == new_id
    assert body["pages"][new_id]["value"] == "3"
    assert not any(f["rule"] == "missing_page" for f in body["findings"])

    plan = client.get(f"/batches/{batch_id}/corrected-plan", headers=AUTH).json()
    item = next(p for p in plan["documents"][0]["pages"] if p["page_id"] == new_id)
    assert item["new_position"] == 3 and item["target_file"].endswith("0003.tif")
    image = client.get(f"/pages/{new_id}/image", params={"max_width": 100}, headers=AUTH)
    assert image.status_code == 200
    saved = client.post(
        f"/batches/{batch_id}/corrected-batch", json={"reviewer": "g1"}, headers=AUTH
    )
    assert saved.status_code == 201, saved.text
    assert saved.json()["totals"]["exported"] == 5
    assert digest(missing_three) == before  # a pasta original não muda

    # Desfazer: a folha sai e a lacuna volta.
    undo = client.delete(f"/batches/{batch_id}/documents/{doc['id']}/pages/{new_id}", headers=AUTH)
    assert undo.status_code == 200, undo.text
    assert new_id not in undo.json()["document"]["page_ids"]
    assert any(f["rule"] == "missing_page" for f in undo.json()["findings"])


def test_explicit_position_and_one_sheet_per_file(client: TestClient, missing_three: Path) -> None:
    report = analyzed(client, missing_three)
    batch_id = report["batch"]["id"]
    doc = report["documents"][0]
    r = client.post(
        f"/batches/{batch_id}/documents/{doc['id']}/pages",
        files={"file": ("folha.tif", sheet_tiff("3"), "image/tiff")},
        data={"reviewer": "g1", "position": "1"},
        headers=AUTH,
    )
    assert r.status_code == 201, r.text
    assert r.json()["position"] == 1 and r.json()["suggested_position"] == 3
    two = io.BytesIO()
    page = Image.new("L", (200, 300), 255)
    page.save(two, format="TIFF", save_all=True, append_images=[page])
    bad = client.post(
        f"/batches/{batch_id}/documents/{doc['id']}/pages",
        files={"file": ("duas.tif", two.getvalue(), "image/tiff")},
        data={"reviewer": "g1"},
        headers=AUTH,
    )
    assert bad.status_code == 422
    original = report["documents"][0]["page_ids"][0]
    refused = client.delete(
        f"/batches/{batch_id}/documents/{doc['id']}/pages/{original}", headers=AUTH
    )
    assert refused.status_code == 409
