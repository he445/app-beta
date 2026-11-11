"""Corrigir tudo, desfazer em lote, página faltando e lote corrigido (ADR-0009)."""

from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from PIL import Image

from qa_engine.application.bulk import SkipCategory, is_automatic, plan_bulk
from qa_engine.application.contracts import validate
from qa_engine.application.corrections import CANONICAL_ORDER, describe_correction
from qa_engine.domain.model import CorrectionAction
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
REVIEWER = "garantidor1"


@pytest.fixture
def client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data["id"] = "test"
    data["resolution"] = {"min_dpi": 150}
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=200,
        workers=1,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def sha_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


def upload(client: TestClient, batch: Path) -> str:
    files = [
        ("files", (f"lote/{p.relative_to(batch).as_posix()}", p.read_bytes(), "image/tiff"))
        for p in sorted(batch.rglob("*.tif"))
    ]
    numbering = (
        "numbering",
        ("n.json", (batch / "numbering.json").read_bytes(), "application/json"),
    )
    r = client.post(
        "/batches", files=[*files, numbering], data={"profile_id": "test"}, headers=AUTH
    )
    assert r.status_code == 202, r.text
    batch_id: str = r.json()["id"]
    for _ in range(300):
        status = client.get(f"/batches/{batch_id}", headers=AUTH).json()
        if status["status"] in {"analyzed", "failed"}:
            assert status["status"] == "analyzed", status
            return batch_id
        time.sleep(0.1)
    raise AssertionError("análise não terminou")


def report(client: TestClient, batch_id: str) -> dict[str, Any]:
    data: dict[str, Any] = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    return data


def run_bulk(client: TestClient, batch_id: str, **scope: str) -> dict[str, Any]:
    body = {"scope": "batch", "reviewer": REVIEWER, **scope}
    r = client.post(f"/batches/{batch_id}/bulk-corrections", json=body, headers=AUTH)
    assert r.status_code == 202, r.text
    validate(r.json(), "bulk-correction.schema.json")
    op_id = r.json()["id"]
    seen: list[int] = []
    for _ in range(600):
        op: dict[str, Any] = client.get(f"/bulk-corrections/{op_id}", headers=AUTH).json()
        seen.append(op["progress"]["done"])
        if op["status"] not in {"queued", "running"}:
            validate(op, "bulk-correction.schema.json")
            assert op["status"] == "applied", op
            assert op["progress"]["done"] == op["progress"]["total"]
            assert seen == sorted(seen)  # progresso real: só cresce
            return op
        time.sleep(0.05)
    raise AssertionError("correção em lote não terminou")


def by_rule(rep: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for f in rep["findings"]:
        out.setdefault(f["rule"], []).append(f)
    return out


def doc_id(rep: dict[str, Any], name: str) -> str:
    return next(d["id"] for d in rep["documents"] if d["name"] == name)


# Regras puras -------------------------------------------------------------------


def test_classification_rules() -> None:
    auto = {
        "id": "f",
        "rule": "skew",
        "severity": "medium",
        "target": {"kind": "page", "id": "p"},
        "correction": {"kind": "automatic", "action": "deskew", "description": "", "params": {}},
    }
    assert is_automatic(auto)
    dup = {
        **auto,
        "rule": "duplicate_page",
        "correction": {**auto["correction"], "action": "remove_page"},
    }
    assert not is_automatic(dup)  # duplicata nunca é removida automaticamente
    blur = {
        **auto,
        "rule": "blur",
        "correction": {"kind": "physical", "action": "rescan", "description": "", "params": {}},
    }
    assert not is_automatic(blur)
    report_ = {
        "documents": [{"id": "d", "name": "D", "page_ids": ["p"], "proposed_order": []}],
        "findings": [auto, dup, blur],
    }
    plan = plan_bulk(report_, "batch", "b")
    assert [u.label for u in plan.units] == ["D · p. 1"]
    assert {s["rule"]: s["category"] for s in plan.skipped} == {
        "duplicate_page": SkipCategory.MANUAL,
        "blur": SkipCategory.NEEDS_RESCAN,
    }


def test_describe_and_canonical_order() -> None:
    assert describe_correction("deskew", {"skew_deg": -2.34}) == "endireitada 2,3°"
    assert describe_correction("autocrop", {}) == "bordas pretas recortadas"
    assert CANONICAL_ORDER[0] is CorrectionAction.AUTOCROP  # recorta antes de girar


# Corrigir tudo -----------------------------------------------------------------


def test_bulk_corrects_only_automatic(client: TestClient, correction_batch: Path) -> None:
    batch_id = upload(client, correction_batch)
    before = report(client, batch_id)
    expected_auto = {f["id"] for f in before["findings"] if is_automatic(f)}
    assert {f["rule"] for f in before["findings"] if f["id"] in expected_auto} == {
        "skew",
        "black_borders",
        "blank_page",
        "out_of_order",
    }

    op = run_bulk(client, batch_id)
    after = report(client, batch_id)
    for f in after["findings"]:
        decision = f.get("decision")
        if f["id"] in expected_auto:
            assert decision is not None, f["rule"]
            assert decision["action"] == "correct"
            assert decision["operation_id"] == op["id"]
            assert decision["reviewer"] == REVIEWER
            assert decision["decided_at"].endswith("Z")
        else:
            assert decision is None, f"{f['rule']} não podia ser decidido automaticamente"

    result = op["result"]
    assert result["applied_by_rule"] == {
        "black_borders": 1,
        "blank_page": 1,
        "out_of_order": 1,
        "skew": 1,
    }
    categories = {(s["rule"], s["category"]) for s in result["skipped"]}
    assert ("missing_page", "missing_page") in categories
    assert ("blur", "needs_rescan") in categories
    assert ("low_resolution", "needs_rescan") in categories
    # 3 páginas (inclinada, borda, branca) + 1 documento (reordenação)
    assert op["progress"]["total"] == 4
    assert op["summary"] == after["batch"]["summary"]

    skew = by_rule(after)["skew"][0]
    page = next(p for p in result["pages"] if p["page_id"] == skew["target"]["id"])
    assert "skew" not in page["remaining_rules"]
    corrected = client.get(f"/pages/{skew['target']['id']}/image?variant=corrected", headers=AUTH)
    assert corrected.status_code == 200

    again = run_bulk(client, batch_id)  # nada automático pendente: operação vazia
    assert again["progress"]["total"] == 0
    assert again["result"]["applied_total"] == 0


def test_bulk_document_scope_touches_only_that_document(
    client: TestClient, correction_batch: Path
) -> None:
    batch_id = upload(client, correction_batch)
    rep = report(client, batch_id)
    doc3 = doc_id(rep, "CX2/DOC3")
    op = run_bulk(client, batch_id, scope="document", document_id=doc3)
    assert op["result"]["applied_by_rule"] == {"blank_page": 1}
    decided = [f["rule"] for f in report(client, batch_id)["findings"] if f.get("decision")]
    assert decided == ["blank_page"]


def test_undo_bulk_restores_exact_state(client: TestClient, correction_batch: Path) -> None:
    batch_id = upload(client, correction_batch)
    before = report(client, batch_id)
    skew_page = by_rule(before)["skew"][0]["target"]["id"]
    assert (
        client.get(f"/pages/{skew_page}/image?variant=corrected", headers=AUTH).status_code == 404
    )

    op = run_bulk(client, batch_id)
    assert report(client, batch_id) != before
    r = client.delete(f"/bulk-corrections/{op['id']}", params={"reviewer": REVIEWER}, headers=AUTH)
    assert r.status_code == 200, r.text
    undone = r.json()
    validate(undone, "bulk-correction.schema.json")
    assert undone["status"] == "undone"
    assert undone["undo"]["undone_total"] == 4

    assert report(client, batch_id) == before
    assert (
        client.get(f"/pages/{skew_page}/image?variant=corrected", headers=AUTH).status_code == 404
    )
    second = client.delete(
        f"/bulk-corrections/{op['id']}", params={"reviewer": REVIEWER}, headers=AUTH
    )
    assert second.status_code == 409


def test_undo_bulk_keeps_decisions_changed_afterwards(
    client: TestClient, correction_batch: Path
) -> None:
    batch_id = upload(client, correction_batch)
    op = run_bulk(client, batch_id)
    blank = by_rule(report(client, batch_id))["blank_page"][0]
    r = client.post(
        f"/findings/{blank['id']}/decision",
        json={"action": "approve", "reviewer": "outro"},
        headers=AUTH,
    )
    assert r.status_code == 200
    client.delete(f"/bulk-corrections/{op['id']}", params={"reviewer": REVIEWER}, headers=AUTH)
    kept = by_rule(report(client, batch_id))["blank_page"][0]
    assert kept["decision"]["action"] == "approve"
    assert kept["decision"]["reviewer"] == "outro"


# Página faltando e lote corrigido -------------------------------------------------------


def test_save_refused_while_missing_page_undecided(
    client: TestClient, correction_batch: Path
) -> None:
    batch_id = upload(client, correction_batch)
    run_bulk(client, batch_id)
    plan = client.get(f"/batches/{batch_id}/corrected-plan", headers=AUTH).json()
    validate(plan, "corrected-plan.schema.json")
    assert plan["can_save"] is False
    assert "CX1/DOC2" in plan["blockers"][0]["message"]
    refused = client.post(
        f"/batches/{batch_id}/corrected-batch", json={"reviewer": REVIEWER}, headers=AUTH
    )
    assert refused.status_code == 409
    assert "faltando" in refused.json()["title"].lower()

    missing = by_rule(report(client, batch_id))["missing_page"][0]
    r = client.post(
        f"/findings/{missing['id']}/decision",
        json={"action": "reject", "reviewer": "conferente"},
        headers=AUTH,
    )
    decision = r.json()["finding"]["decision"]
    assert decision["reviewer"] == "conferente"
    assert decision["decided_at"]
    plan = client.get(f"/batches/{batch_id}/corrected-plan", headers=AUTH).json()
    assert plan["can_save"] is True
    gap = next(d for d in plan["documents"] if d["name"] == "CX1/DOC2")["missing"][0]
    assert gap["missing"] == ["3"]
    assert gap["decision"]["action"] == "reject"


def test_corrected_zip(client: TestClient, correction_batch: Path, tmp_path: Path) -> None:
    source_before = sha_tree(correction_batch)
    batch_id = upload(client, correction_batch)
    stored_input = tmp_path / "data" / "batches" / batch_id / "input"
    input_before = sha_tree(stored_input)
    op = run_bulk(client, batch_id)
    rep = report(client, batch_id)
    missing = by_rule(rep)["missing_page"][0]
    client.post(
        f"/findings/{missing['id']}/decision",
        json={"action": "source_defect", "reviewer": REVIEWER},
        headers=AUTH,
    )

    r = client.post(
        f"/batches/{batch_id}/corrected-batch", json={"reviewer": REVIEWER}, headers=AUTH
    )
    assert r.status_code == 201, r.text
    saved = r.json()
    validate(saved, "corrected-batch.schema.json")
    assert saved["saved_operations"] == [op["id"]]
    assert client.get(f"/bulk-corrections/{op['id']}", headers=AUTH).json()["status"] == "saved"
    assert saved["totals"]["removed"] == 1
    assert saved["totals"]["moved"] == 2

    download = client.get(saved["download"], headers=AUTH)
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert hashlib.sha256(download.content).hexdigest() == saved["sha256"]
    archive = zipfile.ZipFile(io.BytesIO(download.content))
    names = sorted(archive.namelist())
    assert names == sorted(
        [
            *(f"CX1/DOC1/{i:04d}.tif" for i in range(1, 7)),
            *(f"CX1/DOC2/{i:04d}.tif" for i in range(1, 5)),
            "CX2/DOC3/0001.tif",
            "CX2/DOC3/0002.tif",
            "manifest.json",
            "manifest.csv",
            "report.json",
            "findings.csv",
            "decisions.csv",
        ]
    )
    manifest = json.loads(archive.read("manifest.json"))
    validate(manifest, "corrected-manifest.schema.json")
    assert manifest["compression"] == "tiff_deflate"
    docs = {d["name"]: d for d in manifest["documents"]}

    # Ordem pela numeração: a página 4 do arquivo (folha 3) vira a 3, e vice-versa.
    doc1 = {p["old_position"]: p for p in docs["CX1/DOC1"]["pages"]}
    assert docs["CX1/DOC1"]["reordered"] is True
    assert (doc1[3]["new_position"], doc1[4]["new_position"]) == (4, 3)
    assert doc1[3]["moved"] and doc1[4]["moved"]
    assert "movida da posição 4 para a 3" in [c["text"] for c in doc1[4]["changes"]]
    assert doc1[2]["corrected"] and doc1[2]["changes"][0]["text"] == "endireitada 2,5°"
    assert doc1[2]["changes"][0]["decided_by"] == REVIEWER

    # Página em branco fica fora, com o motivo; as outras são renumeradas.
    doc3 = {p["old_position"]: p for p in docs["CX2/DOC3"]["pages"]}
    assert doc3[1]["status"] == "removed"
    assert doc3[1]["reason"] == "em branco"
    assert doc3[1]["target_file"] is None
    assert (doc3[2]["target_file"], doc3[3]["target_file"]) == (
        "CX2/DOC3/0001.tif",
        "CX2/DOC3/0002.tif",
    )
    assert doc3[3][
        "needs_rescan"
    ]  # desfocada e com resolução baixa: exportada como está, sinalizada

    # Decisão sobre a página faltando vai para o manifesto.
    gap = docs["CX1/DOC2"]["missing"][0]
    assert gap["decision"]["action"] == "source_defect"
    assert "source_defect por garantidor1" in archive.read("manifest.csv").decode()

    for doc in manifest["documents"]:
        for page in doc["pages"]:
            if page["status"] != "exported":
                continue
            data = archive.read(page["target_file"])
            assert hashlib.sha256(data).hexdigest() == page["target_sha256"]
            with Image.open(io.BytesIO(data)) as tif:
                assert tif.format == "TIFF"
                assert tif.tag_v2[259] == 8  # Deflate, sem perda (nunca JPEG = 7)
                assert round(tif.info["dpi"][0]) == round(page["dpi"])
                assert tif.tag_v2.get(271) == "Kodak"  # tags de captura preservadas

    # A versão corrigida mais recente é a que vai para o zip.
    skew_item = doc1[2]
    png = client.get(f"/pages/{skew_item['page_id']}/image?variant=corrected", headers=AUTH)
    corrected = np.asarray(Image.open(io.BytesIO(png.content)))
    exported = np.asarray(Image.open(io.BytesIO(archive.read(skew_item["target_file"]))))
    assert np.array_equal(corrected, exported)
    untouched = doc1[1]
    original = client.get(f"/pages/{untouched['page_id']}/image", headers=AUTH)
    assert np.array_equal(
        np.asarray(Image.open(io.BytesIO(original.content))),
        np.asarray(Image.open(io.BytesIO(archive.read(untouched["target_file"])))),
    )
    low_res = doc3[3]
    assert low_res["dpi"] == 100

    # O original nunca é alterado (princípio 2).
    assert sha_tree(correction_batch) == source_before
    assert sha_tree(stored_input) == input_before
