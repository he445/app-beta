"""Tela de Gestão (T23): relatórios de várias máquinas, por conferente, no período."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.application.contracts import validate
from qa_engine.application.management import management_view
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def box(
    box: str,
    reviewer: str,
    machine: str,
    at: str,
    *,
    version: int = 1,
    state: str = "clean",
    pages: int = 10,
    batch: str = "b1",
    program: str = "0.2.0",
) -> dict[str, Any]:
    pending = state == "pending"
    return {
        "schema_version": "1",
        "box": box,
        "batch_id": batch,
        "batch_name": f"Lote {batch}",
        "version": version,
        "state": state,
        "reviewer": reviewer,
        "concluded_at": at,
        "machine": machine,
        "program_version": program,
        "processes": [
            {
                "document_id": "d",
                "number": "PROC-1",
                "pages": pages,
                "missing": {"count": 1 if pending else 0, "folios": ["3"] if pending else []},
                "illegible": {"count": 0, "pages": []},
                "clean": not pending,
            }
        ],
        "totals": {"processes": 1, "pages": pages, "missing": 1 if pending else 0, "illegible": 0},
    }


REPORTS = [
    box("CX1", "ana", "ESTACAO-01", "2026-12-02T10:00:00+00:00", pages=10, program="0.2.0"),
    box(
        "CX2",
        "ana",
        "ESTACAO-01",
        "2026-12-03T10:00:00+00:00",
        pages=20,
        batch="b2",
        program="0.2.0",
    ),
    box(
        "CX9",
        "bia",
        "ESTACAO-02",
        "2026-11-28T10:00:00+00:00",
        state="pending",
        pages=5,
        batch="b3",
        program="0.1.0",
    ),
    box(
        "CX9",
        "bia",
        "ESTACAO-02",
        "2026-12-04T10:00:00+00:00",
        version=2,
        state="resolved",
        pages=5,
        batch="b3",
        program="0.1.0",
    ),
    box(
        "CX5",
        "bia",
        "ESTACAO-02",
        "2026-12-05T10:00:00+00:00",
        state="pending",
        pages=7,
        batch="b4",
        program="0.1.0",
    ),
]


def test_two_machines_together_and_totals_match_the_reports() -> None:
    view = management_view(
        [(f"r{i}", r) for i, r in enumerate(REPORTS)], "2026-12-01", "2027-01-01"
    )
    validate(view, "management.schema.json")
    assert [(r["reviewer"], r["boxes"], r["pages"]) for r in view["reviewers"]] == [
        ("ana", 2, 30),
        ("bia", 1, 7),
    ]
    # CX9 foi concluída em novembro: entra no mês dela, não em dezembro.
    assert view["totals"] == {"boxes": 3, "boxes_pending": 1, "processes": 3, "pages": 37}
    assert {m["machine"]: m["program_version"] for m in view["machines"]} == {
        "ESTACAO-01": "0.2.0",
        "ESTACAO-02": "0.1.0",
    }


def test_state_is_the_latest_version_up_to_the_end_of_the_period() -> None:
    reports = [(f"r{i}", r) for i, r in enumerate(REPORTS)]
    november = management_view(reports, "2026-11-01", "2026-12-01")
    item = november["reviewers"][0]["items"][0]
    assert (item["box"], item["state"], item["version"], item["versions"]) == (
        "CX9",
        "pending",
        1,
        2,
    )
    everything = management_view(reports)
    cx9 = next(b for r in everything["reviewers"] for b in r["items"] if b["box"] == "CX9")
    assert (cx9["state"], cx9["version"]) == ("resolved", 2)
    assert everything["totals"]["boxes"] == 4


@pytest.fixture
def client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data.update({"id": "test"})
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    shared = tmp_path / "rede"
    for i, report in enumerate(REPORTS):
        folder = shared / report["machine"]
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{report['box']}-{i}.json").write_text(json.dumps(report), "utf-8")
    (shared / "ESTACAO-02" / "copiando.json").write_text('{"box": ', "utf-8")
    (tmp_path / "fora.json").write_text(json.dumps(REPORTS[0]), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
        mode="server",
        reports_dir=shared,
    )
    with TestClient(create_app(settings)) as c:
        yield c


def test_management_reads_the_shared_folder(client: TestClient) -> None:
    r = client.get(
        "/management",
        params={"since": "2026-12-01T00:00:00Z", "until": "2027-01-01T00:00:00Z"},
        headers=AUTH,
    )
    assert r.status_code == 200, r.text
    view = r.json()
    assert view["source"] == {"shared": True, "reports": 5, "skipped": 1}
    assert view["totals"]["pages"] == 37
    ref = view["reviewers"][0]["items"][0]["ref"]
    pdf = client.get("/management/report.pdf", params={"ref": ref}, headers=AUTH)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    for bad in ("shared:../fora.json", "shared:ESTACAO-02/copiando.json", "local:nada", "outro"):
        assert (
            client.get("/management/report.pdf", params={"ref": bad}, headers=AUTH).status_code
            == 404
        )
    assert client.get("/management", params={"since": "ontem"}, headers=AUTH).status_code == 422
