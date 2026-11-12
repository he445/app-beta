"""Trava por caixa (T28): aviso com nome e horário, trava abandonada assumida e registrada."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import page_150, save
from qa_engine.adapters.box_locks import FolderBoxLocks, lock_file_name
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.application.box_lock import (
    BoxLockedError,
    BoxLocks,
    boxes_of_files,
    is_abandoned,
)
from qa_engine.application.contracts import validate
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

T0 = datetime(2026, 11, 12, 17, 5, tzinfo=UTC)


class Clock:
    def __init__(self) -> None:
        self.at = T0

    def __call__(self) -> datetime:
        return self.at

    def advance(self, minutes: float) -> None:
        self.at += timedelta(minutes=minutes)


# Caixas do lote ---------------------------------------------------------------------


def test_boxes_follow_the_box_report_rule() -> None:
    rels = [
        "CX0412/PROC-001/0001.tif",
        "CX0412/PROC-002/0001.tif",
        "CX0413/PROC-003/0001.tif",
        "CX0414/processo.pdf",  # documento dentro da pasta: caixa = pasta
        "CX0415/multipagina.tif",
        "Processo 1/0001.tif",  # página única a dois níveis: documento direto no lote
        "solta.tif",
        "numbering.json",
        ".oculta/CX9/x.tif",
        "CX0416/leia-me.txt",
    ]
    boxes = boxes_of_files(rels, "Lote 7", lambda rel: rel == "CX0415/multipagina.tif")
    assert boxes == ["CX0412", "CX0413", "CX0414", "CX0415", "Lote 7"]


# Serviço com duas máquinas na mesma pasta compartilhada --------------------------------


def machine(
    tmp_path: Path, name: str, reviewer: str, clock: Clock, shared: Path | None
) -> BoxLocks:
    data = tmp_path / name
    return BoxLocks(
        FolderBoxLocks(shared, shared=True) if shared is not None else None,
        FolderBoxLocks(data / "travas", shared=False),
        SqliteRepository(data / "qa.sqlite3"),
        machine=name,
        reviewer=reviewer,
        program_version="1.0.0",
        now=clock,
    )


def test_second_machine_is_warned_and_abandoned_lock_can_be_taken_over(tmp_path: Path) -> None:
    clock = Clock()
    shared = tmp_path / "rede" / "travas"
    first = machine(tmp_path, "MAQ-1", "fulano", clock, shared)
    second = machine(tmp_path, "MAQ-2", "beltrana", clock, shared)
    assert first.acquire("lote-a", ["0412", "0413"]) == "shared"

    clock.advance(9)
    with pytest.raises(BoxLockedError) as caught:
        second.acquire("lote-b", ["0412"], take_over=True)  # trava viva nunca é assumida
    lock = caught.value.locks[0]
    validate(lock, "box-lock.schema.json")
    assert (lock["reviewer"], lock["machine"], lock["abandoned"]) == ("fulano", "MAQ-1", False)
    assert lock["since"] == T0.isoformat(timespec="seconds")
    assert lock["message"].startswith("Caixa 0412 em conferência por fulano, na máquina MAQ-1")
    assert not caught.value.can_take_over
    assert not (tmp_path / "MAQ-2" / "qa.sqlite3").exists() or not second.repo.box_holds()

    # A primeira máquina renova: continua viva depois de mais dez minutos.
    first.renew()
    clock.advance(10)
    with pytest.raises(BoxLockedError):
        second.acquire("lote-b", ["0412"])

    # Sem renovação por mais de dez minutos (o programa fechou ou caiu): abandonada.
    clock.advance(1)
    with pytest.raises(BoxLockedError) as caught:
        second.acquire("lote-b", ["0412"])
    assert caught.value.can_take_over and caught.value.locks[0]["abandoned"]
    assert "pode ser assumida" in caught.value.locks[0]["message"]
    assert second.acquire("lote-b", ["0412"], take_over=True) == "shared"

    current = FolderBoxLocks(shared, shared=True).read("0412")
    assert current is not None and current.machine == "MAQ-2"
    assert current.taken_over_from is not None
    assert current.taken_over_from["machine"] == "MAQ-1"
    history = [
        json.loads(line) for line in (shared / "historico.jsonl").read_text("utf-8").splitlines()
    ]
    assert [(h["kind"], h["who"], h["previous"]["reviewer"]) for h in history] == [
        ("taken_over", "beltrana", "fulano")
    ]
    events = second.status("lote-b")["events"]
    assert [(e["kind"], e["previous"]["machine"]) for e in events] == [("taken_over", "MAQ-1")]

    # A primeira máquina volta: perde a 0412 (com quem assumiu) e mantém a 0413.
    first.renew()
    status = first.status("lote-a")
    validate(status, "box-locks.schema.json")
    by_box = {b["box"]: b for b in status["boxes"]}
    assert by_box["0412"]["state"] == "lost"
    assert by_box["0412"]["holder"]["reviewer"] == "beltrana"
    assert by_box["0413"]["state"] == "held"
    assert [e["kind"] for e in status["events"]] == ["acquired", "acquired", "lost"]

    # Caixa concluída: a trava sai da pasta.
    second.release("lote-b", ["0412"])
    assert not (shared / lock_file_name("0412")).exists()
    assert second.status("lote-b")["boxes"][0]["state"] == "released"


def test_same_person_can_reopen_the_own_box(tmp_path: Path) -> None:
    clock = Clock()
    shared = tmp_path / "rede"
    me = machine(tmp_path, "MAQ-1", "fulano", clock, shared)
    me.acquire("lote-a", ["0412"])
    clock.advance(30)  # a própria trava, mesmo abandonada, não pede para assumir
    me.acquire("lote-b", ["0412"])
    me.renew()
    states = {h["batch_id"]: h["state"] for h in me.repo.box_holds()}
    assert states == {"lote-a": "released", "lote-b": "held"}
    lock = FolderBoxLocks(shared, shared=True).read("0412")
    assert lock is not None and lock.batch_id == "lote-b"
    assert not is_abandoned(lock, clock())


def test_without_shared_folder_the_lock_is_local(tmp_path: Path) -> None:
    clock = Clock()
    me = machine(tmp_path, "MAQ-1", "fulano", clock, None)
    assert me.acquire("lote-a", ["0412"]) == "local"
    assert (tmp_path / "MAQ-1" / "travas" / "0412.lock").is_file()
    status = me.status("lote-a")
    assert status["shared_configured"] is False and status["boxes"][0]["scope"] == "local"


def test_shared_folder_offline_falls_back_to_local_and_moves_back(tmp_path: Path) -> None:
    clock = Clock()
    network = tmp_path / "rede"
    network.write_text("compartilhamento fora do ar", "utf-8")  # mkdir falha: OSError
    me = machine(tmp_path, "MAQ-1", "fulano", clock, network / "travas")
    assert me.acquire("lote-a", ["0412"]) == "local"
    clock.advance(1)
    me.renew()  # ainda fora do ar: renovada aqui
    assert me.repo.box_holds()[0]["scope"] == "local"
    network.unlink()
    me.renew()  # voltou: a trava passa para a pasta compartilhada
    assert (network / "travas" / "0412.lock").is_file()
    assert not (tmp_path / "MAQ-1" / "travas" / "0412.lock").exists()
    assert me.repo.box_holds()[0]["scope"] == "shared"


# Rota --------------------------------------------------------------------------------


@pytest.fixture
def box_folder(tmp_path: Path) -> Path:
    root = tmp_path / "Digitalização" / "Caixa 0412"
    for i in range(1, 3):
        save(root / "Processo 1" / f"{i:04d}.tif", page_150(700 + i, i))
    marks = {
        f"Processo 1/{i:04d}.tif#0": [{"readings": [{"text": str(i), "confidence": 0.95}]}]
        for i in range(1, 3)
    }
    (root / "numbering.json").write_text(json.dumps({"pages": marks}), "utf-8")
    return root


def client_for(
    tmp_path: Path, repo: Path, name: str, reviewer: str, clock: Clock, reports: Path | None
) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    data["resolution"] = {"min_dpi": 150}
    (profiles / "sos-piloto.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / name,
        profiles_dir=profiles,
        api_token=None,
        cors_origins=(),
        retention_hours=24 * 365 * 10,
        max_upload_mb=50,
        workers=1,
        mode="desktop",
        output_dir=tmp_path / name / "Saída",
        reports_dir=reports,
    )
    app = create_app(settings)
    engine = app.state.engine
    engine.now = clock
    engine.box_locks.machine = name
    engine.box_locks.reviewer = reviewer
    return TestClient(app)


def wait_analyzed(client: TestClient, batch_id: str) -> None:
    for _ in range(300):
        if client.get(f"/batches/{batch_id}").json()["status"] in {"analyzed", "failed"}:
            return
        time.sleep(0.1)
    raise AssertionError("análise não terminou")


@pytest.fixture
def two_machines(
    tmp_path: Path, repo: Path
) -> Iterator[tuple[TestClient, TestClient, Clock, Path]]:
    clock = Clock()
    reports = tmp_path / "rede" / "relatorios"
    with (
        client_for(tmp_path, repo, "MAQ-1", "fulano", clock, reports) as first,
        client_for(tmp_path, repo, "MAQ-2", "beltrana", clock, reports) as second,
    ):
        yield first, second, clock, reports


def test_second_machine_gets_the_warning_and_takes_over_an_abandoned_box(
    two_machines: tuple[TestClient, TestClient, Clock, Path], box_folder: Path
) -> None:
    first, second, clock, reports = two_machines
    assert "box_locks" in first.get("/health").json()["capabilities"]
    r = first.post("/local-batches", json={"path": str(box_folder)})
    assert r.status_code == 202, r.text
    first_id = r.json()["id"]
    wait_analyzed(first, first_id)
    view = first.get(f"/batches/{first_id}/box-locks").json()
    validate(view, "box-locks.schema.json")
    assert view["boxes"][0]["box"] == "Caixa 0412" and view["boxes"][0]["scope"] == "shared"
    assert (reports / "travas" / "Caixa 0412.lock").is_file()

    clock.advance(5)
    r = second.post("/local-batches", json={"path": str(box_folder), "take_over": True})
    assert r.status_code == 409
    body = r.json()
    validate(body, "box-locked.schema.json")
    assert body["can_take_over"] is False
    assert "Caixa 0412 em conferência por fulano, na máquina MAQ-1, desde" in body["detail"]
    assert body["locks"][0]["since"] == T0.isoformat(timespec="seconds")
    assert second.get("/batches").json() == []  # nada foi aberto

    clock.advance(6)  # 11 minutos sem renovação
    r = second.post("/local-batches", json={"path": str(box_folder)})
    assert r.status_code == 409 and r.json()["can_take_over"] is True
    r = second.post("/local-batches", json={"path": str(box_folder), "take_over": True})
    assert r.status_code == 202, r.text
    second_id = r.json()["id"]
    events = second.get(f"/batches/{second_id}/box-locks").json()["events"]
    assert [(e["kind"], e["who"], e["previous"]["machine"]) for e in events] == [
        ("taken_over", "beltrana", "MAQ-1")
    ]

    # A primeira máquina renova e descobre que a caixa foi assumida.
    first.app.state.engine.renew_box_locks()
    lost = first.get(f"/batches/{first_id}/box-locks").json()["boxes"][0]
    assert lost["state"] == "lost" and lost["holder"]["machine"] == "MAQ-2"

    # A segunda conclui a caixa: o relatório sai e a trava é solta.
    wait_analyzed(second, second_id)
    for f in second.get(f"/batches/{second_id}/findings").json():
        if not f.get("decision"):
            r = second.post(
                f"/findings/{f['id']}/decision", json={"action": "approve", "reviewer": "beltrana"}
            )
            assert r.status_code == 200, r.text
    made = second.post(f"/batches/{second_id}/box-reports", json={"reviewer": "beltrana"})
    assert made.status_code == 200, made.text
    assert not (reports / "travas" / "Caixa 0412.lock").exists()
    released = second.get(f"/batches/{second_id}/box-locks").json()["boxes"][0]
    assert released["state"] == "released"


def test_without_reports_dir_the_screen_knows_the_lock_is_local(
    tmp_path: Path, repo: Path, box_folder: Path
) -> None:
    with client_for(tmp_path, repo, "MAQ-1", "fulano", Clock(), None) as client:
        batch_id = client.post("/local-batches", json={"path": str(box_folder)}).json()["id"]
        wait_analyzed(client, batch_id)
        view: dict[str, Any] = client.get(f"/batches/{batch_id}/box-locks").json()
        assert view["enabled"] and not view["shared_configured"]
        assert view["boxes"][0]["scope"] == "local"
        assert (tmp_path / "MAQ-1" / "travas" / "Caixa 0412.lock").is_file()
