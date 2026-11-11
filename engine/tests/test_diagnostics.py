"""Diagnóstico (ADR-0016): captura, agrupamento, token de administrador e pacote."""

from __future__ import annotations

import io
import json
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.shared_diagnostics import SharedDiagnosticsFolder
from qa_engine.application.admin import AttemptLimiter, hash_token, new_token, verify_token
from qa_engine.application.contracts import validate
from qa_engine.application.diagnostics import (
    groups,
    normalize_message,
    record_from_crash_file,
    record_from_exception,
    summary,
)
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

TOKEN = "token-de-admin-de-teste"
HASH = hash_token(TOKEN)


def boom(path: str) -> None:
    raise ValueError(f"falhou ao ler {path} na página 12")


def test_token_hash_and_attempt_limiter() -> None:
    token = new_token()
    stored = hash_token(token)
    assert stored.startswith("scrypt$16384$8$1$") and token not in stored
    assert verify_token(token, stored) and not verify_token(token + "x", stored)
    assert not verify_token(token, "md5$abc")
    now = {"t": 0.0}
    limiter = AttemptLimiter(lambda: now["t"])
    for _ in range(4):
        limiter.failure()
    assert limiter.blocked_for() == 0
    limiter.failure()
    assert limiter.blocked_for() == 60
    now["t"] = 61
    assert limiter.blocked_for() == 0


def test_same_error_has_same_signature_and_no_absolute_paths() -> None:
    records = []
    for path in (r"C:\Users\maria\lote 1\0001.tif", "/home/ana/lote/7.tif"):
        try:
            boom(path)
        except ValueError as exc:
            records.append(
                record_from_exception(
                    exc, origin="worker", severity="error", where="análise", version="1", user="m"
                )
            )
    assert records[0]["signature"] == records[1]["signature"]
    for r in records:
        assert "maria" not in json.dumps(r) and "/home/ana" not in json.dumps(r)
        assert r["location"].endswith(":boom") or r["location"].endswith("test_diagnostics.py:boom")
    assert normalize_message("lote 0412 página 12 id 3f2a9c1e-1111-2222-3333-444455556666") == (
        "lote # página # id #"
    )


def test_groups_reopen_when_the_error_comes_back() -> None:
    now = datetime(2026, 11, 11, 12, tzinfo=UTC)
    base = {
        "kind": "ValueError",
        "message": "x",
        "location": "a:b",
        "origin": "engine",
        "version": "1",
        "os": "W",
    }
    records: list[dict[str, Any]] = [
        {
            **base,
            "id": "1",
            "signature": "s",
            "severity": "error",
            "machine": "A",
            "at": "2026-11-10T10:00:00Z",
        },
        {
            **base,
            "id": "2",
            "signature": "s",
            "severity": "critical",
            "machine": "B",
            "at": "2026-11-11T10:00:00Z",
        },
    ]
    (group,) = groups(records, {"s": {"resolved_at": "2026-11-10T12:00:00Z", "resolved_by": "ti"}})
    assert (
        group["count"] == 2 and group["machines"] == ["A", "B"] and group["severity"] == "critical"
    )
    assert group["status"] == "open"  # voltou depois da resolução
    (group,) = groups(records, {"s": {"resolved_at": "2026-11-11T11:00:00Z", "resolved_by": "ti"}})
    assert group["status"] == "resolved" and group["resolved_by"] == "ti"
    cards = summary(records, [group], now)
    assert (cards["last_24h"], cards["last_7d"], cards["machines"], cards["open"]) == (1, 2, 2, 0)
    assert cards["per_day"][-1] == {"day": "2026-11-11", "critical": 1, "error": 0, "warning": 0}
    assert len(cards["per_day"]) == 30


def test_crash_file_becomes_a_startup_record() -> None:
    text = (
        "QA 1.0 · 2026-11-11\n\nTraceback (most recent call last):\n"
        '  File "C:\\\\x\\\\qa_engine\\\\entrypoints\\\\desktop\\\\main.py", line 3, in main\n'
        "RuntimeError: porta 5000 ocupada\n"
    )
    record = record_from_crash_file(text, "crash-20261111-101500.txt", "1.0")
    assert record["origin"] == "startup" and record["severity"] == "critical"
    assert record["kind"] == "RuntimeError" and record["at"] == "2026-11-11T10:15:00Z"
    again = record_from_crash_file(text, "crash-20261111-101500.txt", "1.0")
    assert again["id"] == record["id"]  # registrado uma vez só


def make(tmp_path: Path, repo: Path, **overrides: Any) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir(parents=True, exist_ok=True)
    data = yaml.safe_load((repo / "profiles/completo.yaml").read_text("utf-8"))
    (profiles / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    options: dict[str, Any] = {
        "data_dir": tmp_path / "data",
        "profiles_dir": profiles,
        "api_token": None,
        "cors_origins": (),
        "retention_hours": 24,
        "max_upload_mb": 5,
        "workers": 1,
        "admin_token_hash": HASH,
        **overrides,
    }
    return TestClient(create_app(Settings(**options)), raise_server_exceptions=False)


@pytest.fixture
def client(tmp_path: Path, repo: Path) -> Iterator[TestClient]:
    with make(tmp_path, repo, diagnostics_dir=tmp_path / "rede" / "diagnostico") as c:
        yield c


ADMIN = {"X-Admin-Token": TOKEN}


def test_forced_errors_appear_grouped_and_protected(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    engine = client.app.state.engine  # type: ignore[attr-defined]

    # Erro forçado no motor (rota).
    def broken(_: str) -> Any:
        raise RuntimeError(r"falhou em C:\Users\maria\lote\0001.tif")

    monkeypatch.setattr(engine.repo, "get_batch", broken)
    assert client.get("/batches/11111111-1111-1111-1111-111111111111").status_code == 500
    assert client.get("/batches/22222222-2222-2222-2222-222222222222").status_code == 500
    # Erro forçado num processo de análise (o trabalho de fundo registra).
    try:
        raise MemoryError("sem memória no processo de análise")
    except MemoryError as exc:
        engine.record_error(exc, "worker", "análise do lote", "lote-x", "critical")
    # Erro forçado na interface.
    r = client.post(
        "/diagnostics/client-errors",
        json={
            "kind": "TypeError",
            "message": "x is undefined",
            "stack": "TypeError: x\n    at Review (http://127.0.0.1:5000/assets/index.js:1:200)",
            "screen": "#/batches/:id/review",
        },
    )
    assert r.status_code == 204

    assert client.get("/admin/diagnostics").status_code == 401
    assert client.get("/admin/diagnostics", headers={"X-Admin-Token": "errado"}).status_code == 401
    body = client.get("/admin/diagnostics", headers=ADMIN).json()
    validate(body, "diagnostics.schema.json")
    by_origin = {g["origin"]: g for g in body["groups"]}
    assert set(by_origin) == {"engine", "worker", "client"}
    assert by_origin["engine"]["count"] == 2  # as duas rotas quebradas viram um grupo
    assert body["summary"]["open"] == 3 and body["summary"]["last_24h"] == 4
    everything = json.dumps(engine.all_diagnostics())
    assert "maria" not in everything and "C:\\\\Users" not in everything

    signature = by_origin["engine"]["signature"]
    detail = client.get(f"/admin/diagnostics/{signature}", headers=ADMIN).json()
    validate(detail, "diagnostic-detail.schema.json")
    assert len(detail["occurrences"]) == 2 and "RuntimeError" in detail["occurrences"][0]["stack"]
    resolved = client.post(f"/admin/diagnostics/{signature}/resolve", headers=ADMIN).json()
    assert resolved["group"]["status"] == "resolved"
    filtered = client.get("/admin/diagnostics", headers=ADMIN, params={"status": "open"}).json()
    assert signature not in {g["signature"] for g in filtered["groups"]}

    shared = SharedDiagnosticsFolder(tmp_path / "rede" / "diagnostico")
    assert len(shared.read_all()) == 4  # também na pasta compartilhada

    package = client.get("/admin/diagnostics/export", headers=ADMIN)
    assert package.status_code == 200 and package.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(package.content)).namelist()
    assert {"registros.jsonl", "grupos.json", "versao.json", "configuracao.json"} <= set(names)


def test_other_machines_show_up_through_the_shared_folder(tmp_path: Path, repo: Path) -> None:
    folder = tmp_path / "rede"
    other = SharedDiagnosticsFolder(folder, machine="ESTACAO-02")
    try:
        boom("x")
    except ValueError as exc:
        record = record_from_exception(
            exc, origin="engine", severity="error", where="w", version="0.1", user=None
        )
    other.append({**record, "machine": "ESTACAO-02"})
    with make(tmp_path, repo, diagnostics_dir=folder) as c:
        body = c.get("/admin/diagnostics", headers=ADMIN).json()
    assert body["filters"]["machines"] == ["ESTACAO-02"]
    assert body["groups"][0]["machines"] == ["ESTACAO-02"]


def test_lockout_after_five_wrong_tokens_and_off_without_hash(tmp_path: Path, repo: Path) -> None:
    with make(tmp_path, repo) as c:
        for _ in range(5):
            assert c.get("/admin/diagnostics", headers={"X-Admin-Token": "x"}).status_code == 401
        assert c.get("/admin/diagnostics", headers=ADMIN).status_code == 429
    with make(tmp_path / "b", repo, admin_token_hash=None) as c:
        assert c.get("/admin/diagnostics", headers=ADMIN).status_code == 404
        assert c.get("/health").json()["admin"] is False


def test_startup_crash_files_are_ingested_once(tmp_path: Path, repo: Path) -> None:
    logs = tmp_path / "data" / "logs"
    logs.mkdir(parents=True)
    (logs / "crash-20261111-101500.txt").write_text(
        "QA\n\nTraceback\nRuntimeError: porta ocupada\n", "utf-8"
    )
    with make(tmp_path, repo) as c:
        groups_ = c.get("/admin/diagnostics", headers=ADMIN).json()["groups"]
    assert [g["origin"] for g in groups_] == ["startup"]
    assert not (logs / "crash-20261111-101500.txt").exists()
    with make(tmp_path, repo) as c:
        assert len(c.get("/admin/diagnostics", headers=ADMIN).json()["groups"]) == 1


def test_cli_admin_token_writes_only_the_hash(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "maquina" / "config.toml"
    config.parent.mkdir()
    config.write_text('workers = 2\n[locked]\nkeys = ["workers"]\n', "utf-8")
    assert cli(["admin", "token", "--config", str(config)]) == 0
    token = capsys.readouterr().out.splitlines()[1]
    import tomllib

    data = tomllib.loads(config.read_text("utf-8"))
    assert data["workers"] == 2 and data["locked"] == {"keys": ["workers"]}
    assert verify_token(token, data["admin_token_hash"]) and token not in config.read_text("utf-8")


def test_admin_hash_only_from_the_machine_file(tmp_path: Path) -> None:
    from qa_engine.adapters.paths import AppPaths
    from qa_engine.adapters.settings import LayeredSettings
    from qa_engine.application.settings import SettingsError

    paths = AppPaths(tmp_path / "m.toml", tmp_path / "u.toml", tmp_path, tmp_path, tmp_path)
    (tmp_path / "u.toml").write_text(f'admin_token_hash = "{HASH}"\n', "utf-8")
    with pytest.raises(SettingsError) as info:
        LayeredSettings.for_desktop(paths, env={}).load()
    assert info.value.problems[0].key == "admin_token_hash"
    (tmp_path / "u.toml").unlink()
    (tmp_path / "m.toml").write_text(f'admin_token_hash = "{HASH}"\n', "utf-8")
    resolved = LayeredSettings.for_desktop(paths, env={}).load()
    assert resolved.settings.admin_token_hash == HASH
    assert resolved.json()["values"]["admin_token_hash"] is None
    _ = timedelta
