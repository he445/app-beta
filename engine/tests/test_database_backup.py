"""Backup do banco (T29): cópia diária e ao fechar, e ``qa backup restore``."""

from __future__ import annotations

import shutil
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.database_backup import (
    BackupError,
    check_backup,
    list_backups,
    restore_backup,
    take_backup,
)
from qa_engine.adapters.instance import InstanceLock
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

T0 = datetime(2026, 11, 12, 18, 0, tzinfo=UTC)


def fresh_db(path: Path) -> Path:
    SqliteRepository(path).close()
    return path


def test_backup_is_consistent_and_keeps_the_14_newest(tmp_path: Path) -> None:
    db = fresh_db(tmp_path / "data" / "qa.sqlite3")
    folder = tmp_path / "rede" / "MAQ-1" / "maria"
    for day in range(16):
        take_backup(db, folder, T0 + timedelta(days=day))
    kept = list_backups(folder)
    assert len(kept) == 14
    assert kept[0].taken_at == T0 + timedelta(days=15)
    assert kept[-1].taken_at == T0 + timedelta(days=2)
    assert not list(folder.glob("*.part"))
    assert check_backup(kept[0].path) == []


def test_corrupt_or_newer_backup_is_refused(tmp_path: Path) -> None:
    broken = tmp_path / "qa-20261112-180000.sqlite3"
    broken.write_bytes(b"isto nao e um banco" * 100)
    assert check_backup(broken)
    newer = fresh_db(tmp_path / "nova.sqlite3")
    with closing(sqlite3.connect(newer)) as conn, conn:
        conn.execute("INSERT INTO schema_migrations VALUES ('9999_futuro.sql')")
    problems = check_backup(newer)
    assert problems and "versão mais nova" in problems[0]
    with pytest.raises(BackupError):
        restore_backup(newer, tmp_path / "data" / "qa.sqlite3", T0)
    assert not (tmp_path / "data" / "qa.sqlite3").exists()


# Programa desktop --------------------------------------------------------------------


class Clock:
    def __init__(self) -> None:
        self.at = T0

    def __call__(self) -> datetime:
        return self.at


def desktop(tmp_path: Path, repo: Path, backup_dir: Path | None, name: str = "data") -> TestClient:
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
        output_dir=tmp_path / "Saída",
        backup_dir=backup_dir,
    )
    return TestClient(create_app(settings))


def decide_one(client: TestClient, folder: Path) -> tuple[str, str]:
    batch_id = client.post("/local-batches", json={"path": str(folder)}).json()["id"]
    for _ in range(300):
        if client.get(f"/batches/{batch_id}").json()["status"] in {"analyzed", "failed"}:
            break
        time.sleep(0.1)
    finding = client.get(f"/batches/{batch_id}/findings").json()[0]
    r = client.post(
        f"/findings/{finding['id']}/decision", json={"action": "reject", "reviewer": "maria"}
    )
    assert r.status_code == 200, r.text
    return batch_id, finding["id"]


def test_close_backs_up_and_restore_on_a_clean_machine_brings_decisions_back(
    tmp_path: Path, repo: Path, small_batch: Path
) -> None:
    shared = tmp_path / "rede" / "backups"
    with desktop(tmp_path, repo, shared) as client:
        engine = client.app.state.engine  # type: ignore[attr-defined]
        batch_id, finding_id = decide_one(client, small_batch)
        folder = engine.backup_folder
        assert folder.parent.parent == shared  # <backup_dir>/<máquina>/<usuário>
    copies = list_backups(folder)
    assert copies, "ao fechar, o programa copia o banco"

    # Máquina limpa: outra pasta de dados, sem banco.
    clean = tmp_path / "maquina-nova"
    code = cli(["backup", "restore", str(copies[0].path), "--data-dir", str(clean)])
    assert code == 0
    restored = SqliteRepository(clean / "qa.sqlite3")
    try:
        log = restored.decision_log(batch_id)
        assert [(d["finding_id"], d["action"], d["reviewer"]) for d in log] == [
            (finding_id, "reject", "maria")
        ]
        assert [e["kind"] for e in restored.box_lock_events(batch_id)] == ["acquired"]
        assert restored.get_report(batch_id) is not None
    finally:
        restored.close()


def test_restore_keeps_the_current_database_and_refuses_while_the_program_is_open(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    data = tmp_path / "data"
    db = fresh_db(data / "qa.sqlite3")
    backups = tmp_path / "copias"
    assert cli(["backup", "now", "--data-dir", str(data), "--backup-dir", str(backups)]) == 0
    assert (
        cli(["backup", "list", "--all", "--data-dir", str(data), "--backup-dir", str(backups)]) == 0
    )
    assert "qa-" in capsys.readouterr().out

    lock = InstanceLock(data)
    assert lock.acquire()
    try:
        args = [
            "backup",
            "restore",
            "--latest",
            "--data-dir",
            str(data),
            "--backup-dir",
            str(backups),
        ]
        assert cli(args) == 1
        assert "feche o programa" in capsys.readouterr().err
    finally:
        lock.release()
    assert cli(args) == 0
    assert list(data.glob("qa.sqlite3.antes-da-restauracao-*"))
    assert db.is_file()


def test_daily_backup_runs_once_a_day_and_falls_back_when_the_share_is_offline(
    tmp_path: Path, repo: Path
) -> None:
    clock = Clock()
    offline = tmp_path / "rede"
    offline.write_text("compartilhamento fora do ar", "utf-8")
    with desktop(tmp_path, repo, offline / "backups") as client:
        engine: Any = client.app.state.engine  # type: ignore[attr-defined]
        # Sem a rodada de manutenção da abertura (ela usa o relógio real).
        engine._stop.set()
        engine._maintenance.join()
        engine._maintenance = None
        shutil.rmtree(engine.local_backup_folder, ignore_errors=True)
        engine.now = clock
        engine._last_backup = None
        engine._next_backup_try = None
        engine.backup_if_due()
        local = list_backups(engine.local_backup_folder)
        assert len(local) == 1  # a cópia ficou neste computador
        assert any(r["where"] == "cópia do banco" for r in engine.repo.diagnostics())
        clock.at += timedelta(minutes=30)
        engine.backup_if_due()  # sem repetir a falha a cada minuto
        assert len(list_backups(engine.local_backup_folder)) == 1

        offline.unlink()  # a pasta voltou
        clock.at += timedelta(hours=1)
        engine.backup_if_due()
        assert len(list_backups(engine.backup_folder)) == 1
        clock.at += timedelta(hours=2)
        engine.backup_if_due()  # já tem a de hoje
        assert len(list_backups(engine.backup_folder)) == 1
        clock.at += timedelta(hours=24)
        engine.backup_if_due()
        assert len(list_backups(engine.backup_folder)) == 2
