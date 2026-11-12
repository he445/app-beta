"""Relatório por caixa (T22): pendências exatas, caixa limpa e versões."""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.box_report_pdf import render_box_report_pdf
from qa_engine.application.box_report import (
    box_of,
    boxes,
    build_box_report,
    folios_text,
    is_complete,
    pendencies_key,
    process_lines,
)
from qa_engine.application.contracts import validate
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
DECIDED = {"reviewer": "g1", "decided_at": "2026-12-01T10:00:00+00:00"}


def finding(fid: str, rule: str, target: str, action: str | None, **params: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": fid,
        "rule": rule,
        "rule_version": "1.0.0",
        "severity": "high",
        "target": {"kind": "document" if rule == "missing_page" else "page", "id": target},
        "measure": 1.0,
        "threshold": 0.5,
        "confidence": 0.9,
        "message": "x",
        "correction": {
            "kind": "escalate",
            "action": "human_review",
            "description": "x",
            "params": params,
        },
    }
    if action:
        data["decision"] = {"action": action, **DECIDED}
    return data


def fixture_report() -> dict[str, Any]:
    def page(pid: str, file: str, numbering: dict[str, Any] | None = None) -> dict[str, Any]:
        data: dict[str, Any] = {"id": pid, "source_file": file}
        if numbering:
            data["numbering"] = numbering
        return data

    return {
        "batch": {"id": "lote-1", "name": "Lote 1"},
        "documents": [
            {"id": "d1", "name": "CX0412/PROC-001", "page_ids": ["a1", "a2", "a3"]},
            {"id": "d2", "name": "CX0412/PROC-002", "page_ids": ["b1"]},
            {"id": "d3", "name": "CX0413/PROC-003", "page_ids": ["c1"]},
        ],
        "pages": [
            page("a1", "CX0412/PROC-001/0001.tif", {"state": "read", "value": "12"}),
            page(
                "a2",
                "CX0412/PROC-001/0002.tif",
                {"state": "ambiguous", "value": None, "typed": "16"},
            ),
            page("a3", "CX0412/PROC-001/0003.tif", {"state": "illegible", "value": None}),
            page("b1", "CX0412/PROC-002/0001.tif"),
            page("c1", "CX0413/PROC-003/0001.tif"),
        ],
        "findings": [
            finding("m1", "missing_page", "d1", "reject", missing=["13", "14", "15"]),
            finding("f1", "blur", "a2", "reject"),
            finding("f2", "corrupted_file", "a3", "source_defect"),
            finding("f3", "exposure", "a3", "reject"),  # mesma página: conta uma vez
            finding("f4", "skew", "a1", "correct"),  # não é legibilidade
            finding("f5", "blur", "b1", "approve"),  # falso positivo: não é pendência
            finding("f6", "numbering_review", "c1", "approve"),  # número ilegível, página boa
        ],
    }


def build(
    report: dict[str, Any], box: str, version: int = 1, previous_pending: bool = False
) -> dict[str, Any]:
    return build_box_report(
        report,
        box,
        boxes(report)[box],
        reviewer="conferente1",
        concluded_at="2026-12-01T12:00:00+00:00",
        machine="ESTACAO-01",
        program_version="0.2.0",
        version=version,
        previous_pending=previous_pending,
    )


def test_box_with_missing_and_illegible_lists_exactly_the_items() -> None:
    report = fixture_report()
    assert box_of("CX0412/PROC-001", "Lote") == "CX0412" and box_of("PROC", "Lote") == "Lote"
    built = build(report, "CX0412")
    validate(built, "box-report.schema.json")
    first, second = built["processes"]
    assert first["number"] == "PROC-001"
    assert first["missing"] == {"count": 3, "folios": ["13", "14", "15"]}
    assert first["illegible"] == {
        "count": 2,
        "pages": [
            {"folio": "16", "position": 2, "file": "0002.tif"},
            {"folio": None, "position": 3, "file": "0003.tif"},
        ],
    }
    assert process_lines(first) == [
        "Páginas faltando: 3 — fls. 13, 14 e 15",
        "Páginas ilegíveis: 2 — fls. 16, posição 3 (0003.tif)",
    ]
    assert second["clean"] and process_lines(second) == ["Nenhuma pendência"]
    assert built["state"] == "pending"
    assert built["totals"] == {"processes": 2, "pages": 4, "missing": 3, "illegible": 2}
    assert folios_text(["7"]) == "fls. 7"


def test_clean_box_says_no_pendency_and_pdf_renders() -> None:
    built = build(fixture_report(), "CX0413")
    assert built["state"] == "clean" and process_lines(built["processes"][0]) == [
        "Nenhuma pendência"
    ]
    pdf = render_box_report_pdf(built)
    assert pdf.startswith(b"%PDF") and pdf == render_box_report_pdf(built)


def test_box_is_complete_only_without_pending_decisions() -> None:
    report = fixture_report()
    assert is_complete(report, boxes(report)["CX0412"])
    report["findings"].append(finding("p1", "skew", "b1", None))
    assert not is_complete(report, boxes(report)["CX0412"])


def test_resolved_pendency_changes_the_key_and_the_state() -> None:
    report = fixture_report()
    v1 = build(report, "CX0412")
    for f in report["findings"]:
        f["decision"] = {"action": "approve", **DECIDED}
    v2 = build(report, "CX0412", version=2, previous_pending=True)
    assert pendencies_key(v1) != pendencies_key(v2)
    assert v2["state"] == "resolved" and v2["totals"]["missing"] == 0
    same = build(report, "CX0412", version=3, previous_pending=False)
    assert pendencies_key(same) == pendencies_key(v2)


# Pela API: gerar ao concluir, gravar nas duas pastas, reabrir gera a v2 ------------


@pytest.fixture
def client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data.update({"id": "test", "resolution": {"min_dpi": 150}})
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
        mode="server",
        output_dir=tmp_path / "saida",
        reports_dir=tmp_path / "rede" / "relatorios",
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_reports_are_written_and_reopening_keeps_v1(
    client: TestClient, small_batch: Path, tmp_path: Path
) -> None:
    files = [
        ("files", (f"lote/{p.relative_to(small_batch).as_posix()}", p.read_bytes(), "image/tiff"))
        for p in sorted(small_batch.rglob("*.tif"))
    ]
    batch_id = client.post(
        "/batches", files=files, data={"profile_id": "test"}, headers=AUTH
    ).json()["id"]
    for _ in range(200):
        if client.get(f"/batches/{batch_id}", headers=AUTH).json()["status"] == "analyzed":
            break
        time.sleep(0.1)
    report = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
    # Nada concluído ainda: nenhum relatório.
    assert (
        client.post(
            f"/batches/{batch_id}/box-reports", json={"reviewer": "g1"}, headers=AUTH
        ).json()
        == []
    )
    blur = next(f for f in report["findings"] if f["rule"] == "blur")
    for f in report["findings"]:
        action = "reject" if f["id"] == blur["id"] else "approve"
        r = client.post(
            f"/findings/{f['id']}/decision", json={"action": action, "reviewer": "g1"}, headers=AUTH
        )
        assert r.status_code == 200, r.text
    made = client.post(
        f"/batches/{batch_id}/box-reports", json={"reviewer": "g1"}, headers=AUTH
    ).json()
    assert [m["report"]["version"] for m in made] == [1]
    v1 = made[0]["report"]
    assert v1["box"] == "CX1" and v1["state"] == "pending" and v1["totals"]["illegible"] == 1
    # Sem mudança, não sai versão nova.
    assert (
        client.post(
            f"/batches/{batch_id}/box-reports", json={"reviewer": "g1"}, headers=AUTH
        ).json()
        == []
    )
    pdf = client.get(f"/box-reports/{made[0]['id']}.pdf", headers=AUTH)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")

    # O retrabalho voltou: a decisão muda e a caixa é reaberta.
    client.delete(f"/findings/{blur['id']}/decision", headers=AUTH)
    client.post(
        f"/findings/{blur['id']}/decision",
        json={"action": "approve", "reviewer": "g1"},
        headers=AUTH,
    )
    v2 = client.post(
        f"/batches/{batch_id}/box-reports", json={"reviewer": "g1"}, headers=AUTH
    ).json()
    assert [(m["report"]["version"], m["report"]["state"]) for m in v2] == [(2, "resolved")]
    listed = client.get(f"/batches/{batch_id}/box-reports", headers=AUTH).json()
    assert [item["report"]["version"] for item in listed] == [1, 2]

    local = tmp_path / "saida" / "Relatórios por caixa" / "lote"
    assert {p.name for p in local.iterdir()} == {
        "CX1-v1.json",
        "CX1-v1.pdf",
        "CX1-v2.json",
        "CX1-v2.pdf",
    }
    shared = list((tmp_path / "rede" / "relatorios").rglob("*.json"))
    assert len(shared) == 2 and all(p.name.startswith("CX1-") for p in shared)
