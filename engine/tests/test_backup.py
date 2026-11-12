"""Backup do banco local e restauração numa máquina limpa (T29)."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.backup import KEEP, check, list_backups, prune
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "segredo-de-teste"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_restoring_a_backup_on_a_clean_machine_brings_back_decisions_and_audit(
    tmp_path: Path, full_profile_path: Path, small_batch: Path
) -> None:
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data.update({"id": "test", "resolution": {"min_dpi": 150}})
    (profiles / "test.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    shared = tmp_path / "rede" / "backups"
    settings = Settings(
        data_dir=tmp_path / "maquina-velha",
        profiles_dir=profiles,
        api_token=TOKEN,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
        mode="server",
        backup_dir=shared,
    )
    with TestClient(create_app(settings)) as client:
        files = [
            (
                "files",
                (f"lote/{p.relative_to(small_batch).as_posix()}", p.read_bytes(), "image/tiff"),
            )
            for p in sorted(small_batch.rglob("*.tif"))
        ]
        batch_id = client.post(
            "/batches", files=files, data={"profile_id": "test"}, headers=AUTH
        ).json()["id"]
        for _ in range(200):
            if client.get(f"/batches/{batch_id}", headers=AUTH).json()["status"] == "analyzed":
                break
            time.sleep(0.1)
        finding = client.get(f"/batches/{batch_id}/report", headers=AUTH).json()["findings"][0]
        r = client.post(
            f"/findings/{finding['id']}/decision",
            json={"action": "approve", "reviewer": "ana"},
            headers=AUTH,
        )
        assert r.status_code == 200
    copies = [p for folder in shared.iterdir() for p in list_backups(folder)]
    assert copies, "fechar o programa grava uma cópia"
    latest = max(copies, key=lambda p: p.name)
    assert check(latest) is None

    clean = tmp_path / "maquina-nova"
    assert cli(["backup", "restore", str(latest), "--data-dir", str(clean)]) == 0
    repo = SqliteRepository(clean / "qa.sqlite3")
    try:
        log = repo.decision_log(batch_id)
        assert [(d["finding_id"], d["action"], d["reviewer"]) for d in log] == [
            (finding["id"], "approve", "ana")
        ]
        restored = next(f for f in repo.findings(batch_id) if f["id"] == finding["id"])
        assert restored["decision"]["reviewer"] == "ana"
    finally:
        repo.close()


def test_only_the_newest_copies_are_kept_and_bad_copies_are_refused(tmp_path: Path) -> None:
    folder = tmp_path / "backups"
    folder.mkdir()
    for day in range(1, KEEP + 4):
        (folder / f"qa-202612{day:02d}-180000.sqlite3").write_bytes(b"x")
    removed = prune(folder)
    assert len(removed) == 3 and list_backups(folder)[0].name == "qa-20261204-180000.sqlite3"

    bad = tmp_path / "estranho.sqlite3"
    sqlite3.connect(bad).execute("CREATE TABLE x (a)").connection.commit()
    assert check(bad) == "não é um banco do programa"
    assert cli(["backup", "restore", str(bad), "--data-dir", str(tmp_path / "dados")]) == 1
    assert not (tmp_path / "dados" / "qa.sqlite3").exists()


def test_update_copies_the_database_first_and_going_back_restores_that_copy(tmp_path: Path) -> None:
    from importlib import resources

    import pytest

    from qa_engine.adapters.sqlite import NewerDatabaseError

    data_dir = tmp_path / "dados"
    data_dir.mkdir()
    database = data_dir / "qa.sqlite3"
    # Banco da versão anterior: só a primeira migração aplicada.
    first = (resources.files("qa_engine.adapters") / "migrations" / "0001_init.sql").read_text(
        "utf-8"
    )
    conn = sqlite3.connect(database)
    conn.executescript(
        "CREATE TABLE schema_migrations (name TEXT PRIMARY KEY);"
        + first
        + "\nINSERT INTO schema_migrations VALUES ('0001_init.sql');"
    )
    conn.close()

    before = data_dir / "backups" / "antes-de-atualizar"
    SqliteRepository(database, before_update_dir=before).close()  # a versão nova abre
    copies = list(before.iterdir())
    assert len(copies) == 1 and copies[0].name.startswith("qa-antes-de-atualizar-0001_init-")
    old = sqlite3.connect(copies[0])
    assert [r[0] for r in old.execute("SELECT name FROM schema_migrations")] == ["0001_init.sql"]
    old.close()

    # A versão nova aplicou migrações que a anterior não conhece: ela recusa abrir.
    conn = sqlite3.connect(database)
    conn.execute("INSERT INTO schema_migrations VALUES ('9999_futuro.sql')")
    conn.commit()
    conn.close()
    with pytest.raises(NewerDatabaseError) as refused:
        SqliteRepository(database)
    assert refused.value.migrations == ["9999_futuro.sql"]

    # Voltar versão: restaurar a cópia de antes da atualização.
    assert cli(["backup", "restore", "--before-update", "--data-dir", str(data_dir)]) == 0
    SqliteRepository(database).close()  # abre de novo (e reaplica o que falta)
    assert any(p.name.startswith("qa.sqlite3.antes-da-restauracao-") for p in data_dir.iterdir())
