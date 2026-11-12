"""Liberação por processo (T25, ADR-0018)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import cv2
import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import page_150, save
from qa_engine.application.analyze import BatchAnalysis
from qa_engine.application.profile import Profile
from qa_engine.application.release import merge_release
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis
from qa_engine.entrypoints.http import app as http_app
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
DECIDED = {"action": "approve", "reviewer": "g1", "decided_at": "2026-12-01T10:00:00+00:00"}


@pytest.fixture
def two_processes(tmp_path: Path) -> Path:
    """DOC1 com 3 páginas e DOC2 com 2; a 3 do DOC1 é cópia (menos nítida) da 1 do DOC2."""
    root = tmp_path / "lote"
    for i in (1, 2):
        save(root / f"CX1/DOC1/{i:04d}.tif", page_150(10 + i, i))
    twin = page_150(99, 3)
    save(root / "CX1/DOC1/0003.tif", cv2.GaussianBlur(twin, (0, 0), 0.7))
    save(root / "CX1/DOC2/0001.tif", twin)
    save(root / "CX1/DOC2/0002.tif", page_150(21, 2))
    return root


def test_first_process_is_released_without_cross_process_rules(
    two_processes: Path, test_profile: Profile
) -> None:
    partials: list[tuple[BatchAnalysis, str]] = []
    final = run_analysis(
        two_processes, test_profile, workers=1, on_document=lambda a, d: partials.append((a, d))
    )
    assert len(partials) == 1  # o último processo sai na passada final
    partial, doc_id = partials[0]
    assert not partial.final and [d.name for d in partial.documents] == ["CX1/DOC1"]
    assert doc_id == partial.documents[0].id
    assert [name for _, name in partial.pending_documents] == ["CX1/DOC2"]
    assert len(partial.pages) == 3
    assert not any(f.rule == "duplicate_page" for f in partial.findings)
    assert final.final and any(f.rule == "duplicate_page" for f in final.findings)

    # O conferente decide tudo do DOC1 antes de a caixa terminar.
    previous = merge_release(None, analysis_json(partial), test_profile, two_processes, final=False)
    for finding in previous["findings"]:
        finding["decision"] = dict(DECIDED)
    decided = {f["id"] for f in previous["findings"]}
    merged = merge_release(previous, analysis_json(final), test_profile, two_processes, final=True)
    by_id = {f["id"]: f for f in merged["findings"]}
    assert all(by_id[fid].get("decision") == DECIDED for fid in decided)  # nada se perde
    duplicate = next(f for f in merged["findings"] if f["rule"] == "duplicate_page")
    doc1 = next(d for d in merged["documents"] if d["name"] == "CX1/DOC1")
    assert duplicate["target"]["id"] in doc1["page_ids"] and "decision" not in duplicate
    new_in_doc1 = [
        f["id"]
        for f in merged["findings"]
        if f["id"] not in decided and f["target"]["id"] in {doc1["id"], *doc1["page_ids"]}
    ]
    assert doc1["reevaluate"] == sorted(new_in_doc1) and duplicate["id"] in doc1["reevaluate"]
    doc2 = next(d for d in merged["documents"] if d["name"] == "CX1/DOC2")
    assert "reevaluate" not in doc2  # ninguém tinha conferido o DOC2


@pytest.fixture
def gated(monkeypatch: pytest.MonkeyPatch) -> Iterator[threading.Event]:
    """A análise para depois de liberar o primeiro processo até o teste deixar seguir."""
    gate = threading.Event()
    real = http_app.run_analysis

    def slow(*args: Any, **kwargs: Any) -> BatchAnalysis:
        release = kwargs["on_document"]

        def hold(partial: BatchAnalysis, doc: str) -> None:
            release(partial, doc)
            assert gate.wait(30), "o teste não liberou a análise"

        return real(*args, **{**kwargs, "on_document": hold})

    monkeypatch.setattr(http_app, "run_analysis", slow)
    yield gate
    gate.set()


def test_reviewer_opens_the_first_process_while_the_box_is_analyzed(
    tmp_path: Path, full_profile_path: Path, two_processes: Path, gated: threading.Event
) -> None:
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
    )
    with TestClient(create_app(settings)) as client:
        files = [
            (
                "files",
                (f"lote/{p.relative_to(two_processes).as_posix()}", p.read_bytes(), "image/tiff"),
            )
            for p in sorted(two_processes.rglob("*.tif"))
        ]
        batch_id = client.post(
            "/batches", files=files, data={"profile_id": "test"}, headers=AUTH
        ).json()["id"]
        status: dict[str, Any] = {}
        for _ in range(300):
            status = client.get(f"/batches/{batch_id}", headers=AUTH).json()
            if status.get("documents", {}).get("ready"):
                break
            time.sleep(0.05)
        assert status["status"] == "processing"
        assert [d["name"] for d in status["documents"]["ready"]] == ["CX1/DOC1"]
        assert [d["name"] for d in status["documents"]["pending"]] == ["CX1/DOC2"]
        report = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
        assert [d["name"] for d in report["documents"]] == ["CX1/DOC1"]
        # Conferir já é possível; o que depende do lote inteiro espera a passada final.
        first = report["findings"][0]
        r = client.post(
            f"/findings/{first['id']}/decision",
            json={"action": "approve", "reviewer": "g1"},
            headers=AUTH,
        )
        assert r.status_code == 200, r.text
        assert (
            client.post(
                f"/batches/{batch_id}/box-reports", json={"reviewer": "g1"}, headers=AUTH
            ).status_code
            == 409
        )
        bulk = client.post(
            f"/batches/{batch_id}/bulk-corrections",
            json={"scope": "batch", "reviewer": "g1"},
            headers=AUTH,
        )
        assert bulk.status_code == 409

        gated.set()
        for _ in range(300):
            status = client.get(f"/batches/{batch_id}", headers=AUTH).json()
            if status["status"] == "analyzed":
                break
            time.sleep(0.05)
        assert status["status"] == "analyzed" and "documents" not in status
        final = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()
        assert [d["name"] for d in final["documents"]] == ["CX1/DOC1", "CX1/DOC2"]
        kept = next(f for f in final["findings"] if f["id"] == first["id"])
        assert kept["decision"]["action"] == "approve"
        events = client.get(f"/batches/{batch_id}/events", headers=AUTH).text
        assert "event: done" in events
