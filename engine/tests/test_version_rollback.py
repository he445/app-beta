"""Voltar versão e versão por máquina (T31)."""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine import __version__
from qa_engine.adapters.database_backup import (
    UPDATES_FOLDER,
    DatabaseNewerError,
    prepare_database,
    restore_before_update,
    update_copies,
)
from qa_engine.adapters.shared_reports import SharedReportsFolder
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.application.contracts import validate
from qa_engine.application.management import management_view, version_key
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.entrypoints.desktop.main import offer_rollback, rollback_page
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

NOW = datetime(2026, 11, 12, 19, 0, tzinfo=UTC)
LAST = "0012_program_versions.sql"


def settings_for(tmp_path: Path, repo: Path, reports: Path | None = None) -> Settings:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    data["resolution"] = {"min_dpi": 150}
    (profiles / "sos-piloto.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=None,
        cors_origins=(),
        retention_hours=24 * 365 * 10,
        max_upload_mb=50,
        workers=1,
        mode="desktop",
        output_dir=tmp_path / "Saída",
        reports_dir=reports,
    )


def as_previous_version(db: Path) -> None:
    """Deixa o banco como a versão anterior o deixou (sem a última migração)."""
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("DELETE FROM schema_migrations WHERE name = ?", (LAST,))
        conn.execute("DROP TABLE program_versions")


def as_newer_version(db: Path, version: str = "9.9.9") -> None:
    """Simula a versão nova: uma migração que esta versão não conhece."""
    with closing(sqlite3.connect(db)) as conn, conn:
        conn.execute("INSERT INTO schema_migrations VALUES ('9999_futuro.sql')")
        conn.execute("CREATE TABLE futuro (x INTEGER)")
        conn.execute(
            "INSERT INTO program_versions VALUES (?, ?, ?)",
            (version, "2026-12-01T00:00:00+00:00", "2026-12-01T00:00:00+00:00"),
        )


def test_update_copies_the_database_before_migrating(tmp_path: Path) -> None:
    db = tmp_path / "qa.sqlite3"
    assert prepare_database(db, __version__, NOW) is None  # máquina limpa
    SqliteRepository(db).close()
    assert prepare_database(db, __version__, NOW) is None  # nada a migrar
    as_previous_version(db)
    copy = prepare_database(db, __version__, NOW)
    assert copy is not None and copy.parent == tmp_path / UPDATES_FOLDER
    assert copy.name.startswith(f"qa-antes-da-{__version__}-de-")
    repo = SqliteRepository(db)  # migra
    repo.close()
    assert update_copies(db) == [copy]


def test_previous_version_refuses_a_newer_database_and_changes_nothing(tmp_path: Path) -> None:
    db = tmp_path / "qa.sqlite3"
    SqliteRepository(db).close()
    as_newer_version(db, "1.4.0")
    before = db.read_bytes()
    with pytest.raises(DatabaseNewerError) as caught:
        prepare_database(db, __version__, NOW)
    assert caught.value.version == "1.4.0"
    assert caught.value.migrations == ["9999_futuro.sql"]
    assert "versão 1.4.0" in str(caught.value)
    assert db.read_bytes() == before


def decide(client: TestClient, folder: Path) -> tuple[str, str]:
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


def test_going_back_to_the_previous_version_keeps_the_decisions(
    tmp_path: Path, repo: Path, small_batch: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = settings_for(tmp_path, repo)
    db = settings.data_dir / "qa.sqlite3"
    # Versão anterior em uso: uma decisão tomada.
    with TestClient(create_app(settings)) as client:
        batch_id, finding_id = decide(client, small_batch)
    as_previous_version(db)

    # Atualiza: a versão nova copia o banco e migra.
    with TestClient(create_app(settings)) as client:
        assert client.app.state.engine.update_copy is not None  # type: ignore[attr-defined]
    as_newer_version(db)

    # A versão nova veio com problema: a anterior é aberta de novo.
    started = time.monotonic()
    with pytest.raises(DatabaseNewerError):
        create_app(settings)
    assert offer_rollback(db, DatabaseNewerError(["9999_futuro.sql"], "9.9.9"), True) == 4
    assert "backup restore --before-update" in capsys.readouterr().err
    copy, kept = restore_before_update(db, NOW)
    assert kept is not None and kept.is_file()  # o banco da versão nova fica guardado
    with TestClient(create_app(settings)) as client:
        log = client.app.state.engine.repo.decision_log(batch_id)  # type: ignore[attr-defined]
        assert [(d["finding_id"], d["reviewer"]) for d in log] == [(finding_id, "maria")]
    assert time.monotonic() - started < 300  # bem menos que 5 minutos

    page = rollback_page("banco mais novo", [copy.name])
    assert "Restaurar a cópia de antes da atualização" in page and copy.name in page


def test_cli_restores_the_copy_from_before_the_update(tmp_path: Path) -> None:
    data = tmp_path / "data"
    db = data / "qa.sqlite3"
    SqliteRepository(db).close()
    as_previous_version(db)
    assert prepare_database(db, __version__, NOW) is not None
    SqliteRepository(db).close()
    as_newer_version(db)
    assert cli(["backup", "restore", "--before-update", "--data-dir", str(data)]) == 0
    assert prepare_database(db, __version__, NOW) is None  # já migrado: abre direto
    with closing(sqlite3.connect(db)) as conn, conn:
        names = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    assert "9999_futuro.sql" not in names and LAST in names


# Versão por máquina --------------------------------------------------------------------


def test_management_flags_machines_on_an_older_version() -> None:
    assert version_key("1.10.0") > version_key("1.9.3")  # type: ignore[operator]
    seen = [
        {
            "machine": "MAQ-1",
            "program_version": "1.1.0",
            "last_seen_at": "2026-11-12T10:00:00+00:00",
        },
        {
            "machine": "MAQ-2",
            "program_version": "1.0.0",
            "last_seen_at": "2026-11-12T09:00:00+00:00",
        },
    ]
    view = management_view([], seen=seen)
    validate(view, "management.schema.json")
    machines = {m["machine"]: m for m in view["machines"]}
    assert machines["MAQ-2"]["outdated"] and not machines["MAQ-1"]["outdated"]
    assert machines["MAQ-2"]["last_report_at"] == ""  # abriu, mas ainda sem relatório


def test_each_machine_announces_its_version_in_the_shared_folder(
    tmp_path: Path, repo: Path
) -> None:
    reports = tmp_path / "rede" / "relatorios"
    folder = SharedReportsFolder(reports)
    folder.write_machine(
        {
            "machine": "ESTACAO-ANTIGA",
            "program_version": "0.0.1",
            "last_seen_at": "2026-11-01T08:00:00+00:00",
        }
    )
    with TestClient(create_app(settings_for(tmp_path, repo, reports))) as client:
        engine = client.app.state.engine  # type: ignore[attr-defined]
        engine.announce_machine()
        mine = engine.machine_info()["machine"]
        files = sorted(p.name for p in (reports / "maquinas").glob("*.json"))
        assert len(files) == 2
        view = client.get("/management").json()
        validate(view, "management.schema.json")
        machines = {m["machine"]: m for m in view["machines"]}
        assert machines[mine]["program_version"] == __version__
        assert not machines[mine]["outdated"]
        assert machines["ESTACAO-ANTIGA"]["outdated"]
        assert view["source"]["skipped"] == 0  # maquinas/ não é lida como relatório
    record = json.loads((reports / "maquinas" / f"{mine}.json").read_text("utf-8"))
    assert record["program_version"] == __version__
