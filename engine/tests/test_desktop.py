"""Programa desktop (ADR-0011): abertura, segurança do endereço local e instância única."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.adapters.instance import InstanceLock
from qa_engine.adapters.logs import mask_paths, write_crash
from qa_engine.entrypoints.desktop.main import Bridge, desktop_settings, error_page, free_port
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings


def base_settings(tmp_path: Path, repo: Path) -> Settings:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    (profiles / "sos-piloto.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    return Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=None,
        cors_origins=("https://qualquer.exemplo",),
        retention_hours=24,
        max_upload_mb=10,
        workers=1,
    )


@pytest.fixture
def desktop(tmp_path: Path, repo: Path) -> Iterator[tuple[TestClient, Settings]]:
    settings = desktop_settings(base_settings(tmp_path, repo), 51234, "token-desta-abertura")
    app = create_app(settings)
    with TestClient(app, base_url="http://127.0.0.1:51234") as client:
        yield client, settings


def test_desktop_settings_lock_down_the_local_address(tmp_path: Path, repo: Path) -> None:
    settings = desktop_settings(base_settings(tmp_path, repo), 51234, "t" * 32)
    assert settings.mode == "desktop"
    assert settings.api_token == "t" * 32
    assert settings.cors_origins == ()
    assert settings.trusted_hosts == ("127.0.0.1:51234", "localhost:51234")
    assert 1024 < free_port() < 65536


def test_api_needs_the_token_and_the_right_host(
    desktop: tuple[TestClient, Settings],
) -> None:
    client, _ = desktop
    assert client.get("/health").status_code == 200
    assert client.get("/batches").status_code == 401
    auth = {"Authorization": "Bearer token-desta-abertura"}
    assert client.get("/batches", headers=auth).status_code == 200
    # Outro site na máquina chamando 127.0.0.1 com outro nome (DNS rebinding).
    evil = client.get("/batches", headers={**auth, "Host": "atacante.exemplo:51234"})
    assert evil.status_code == 400
    assert client.get("/health", headers={"Host": "localhost:51234"}).status_code == 200
    # Nenhum CORS liberado.
    pre = client.options(
        "/batches",
        headers={"Origin": "https://qualquer.exemplo", "Access-Control-Request-Method": "GET"},
    )
    assert "access-control-allow-origin" not in pre.headers


def test_one_time_code_is_exchanged_once(desktop: tuple[TestClient, Settings]) -> None:
    client, _ = desktop
    engine = client.app.state.engine  # type: ignore[attr-defined]
    code = engine.issue_code()
    r = client.post("/session/exchange", json={"code": code})
    assert r.status_code == 200 and r.json() == {"token": "token-desta-abertura"}
    assert client.post("/session/exchange", json={"code": code}).status_code == 403
    assert client.post("/session/exchange", json={"code": "x" * 32}).status_code == 403
    assert client.post("/session/exchange", json={"code": "curto"}).status_code == 422


def test_code_exchange_does_not_exist_outside_desktop(tmp_path: Path, repo: Path) -> None:
    with TestClient(create_app(base_settings(tmp_path, repo))) as client:
        assert client.post("/session/exchange", json={"code": "x" * 32}).status_code == 404
        assert client.post("/desktop/focus").status_code == 404


def test_focus_requires_the_instance_secret(desktop: tuple[TestClient, Settings]) -> None:
    client, _ = desktop
    calls: list[int] = []
    client.app.state.focus_secret = "segredo-da-instancia"  # type: ignore[attr-defined]
    client.app.state.focus_handler = lambda: calls.append(1)  # type: ignore[attr-defined]
    assert client.post("/desktop/focus").status_code == 404
    assert client.post("/desktop/focus", headers={"X-Instance-Secret": "errado"}).status_code == 404
    ok = client.post("/desktop/focus", headers={"X-Instance-Secret": "segredo-da-instancia"})
    assert ok.status_code == 204 and calls == [1]


def test_bridge_gives_the_token_and_no_folder_without_window() -> None:
    bridge = Bridge("abc")
    assert bridge.get_session() == {"token": "abc"}
    assert bridge.pick_folder() is None


def test_instance_lock_is_exclusive(tmp_path: Path) -> None:
    first = InstanceLock(tmp_path)
    assert first.acquire()
    first.publish(51234, "s")
    second = InstanceLock(tmp_path)
    assert not second.acquire()
    assert second.owner() == {"port": 51234, "secret": "s", "pid": os.getpid()}
    first.release()
    assert second.acquire()
    second.release()


def test_logs_never_keep_absolute_paths(tmp_path: Path) -> None:
    text = r"erro em C:\Users\maria\Documentos\lote 1\0001.tif e \\srv\digit\x e /home/ana/l"
    masked = mask_paths(text)
    assert masked.startswith("erro em <caminho>") and masked.endswith("<caminho>")
    assert not any(x in masked for x in ("maria", "lote 1", "srv", "ana"))
    try:
        raise RuntimeError(r"falhou ao ler C:\Users\maria\x.tif")
    except RuntimeError as exc:
        crash = write_crash(tmp_path, exc, "9.9.9")
    content = crash.read_text("utf-8")
    assert "maria" not in content and "RuntimeError" in content and "9.9.9" in content


def test_error_page_escapes_the_problem() -> None:
    page = error_page(["workers em <arquivo>: esperado ≥ 1"], "Configuração inválida")
    assert "&lt;arquivo&gt;" in page and "<arquivo>" not in page


def _env(home: Path) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.startswith("QA_")}
    env.update(
        HOME=str(home),
        XDG_DATA_HOME=str(home / "dados"),
        XDG_CONFIG_HOME=str(home / "config"),
        XDG_CONFIG_DIRS=str(home / "maquina"),
        QA_BATCH_SETTLE_SECONDS="0",
        QA_WORKERS="1",
    )
    return env


def test_headless_start_single_instance_and_invalid_settings(tmp_path: Path) -> None:
    """Abre de verdade (sem janela), a segunda abertura só traz a primeira, e erro de
    configuração para com código 2 dizendo a chave."""
    command = [sys.executable, "-m", "qa_engine.entrypoints.desktop", "--headless"]
    first = subprocess.Popen(
        command, env=_env(tmp_path), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        line = first.stdout.readline() if first.stdout else ""
        assert line.startswith("motor em http://127.0.0.1:"), (
            line,
            first.stderr.read() if first.stderr else "",
        )
        url = line.split()[-1]
        with urllib.request.urlopen(f"{url}/health", timeout=5) as response:
            health = json.loads(response.read())
        assert health["mode"] == "desktop" and health["auth_required"] is True
        assert "os_session" in health["capabilities"]

        started = time.monotonic()
        second = subprocess.run(
            command, env=_env(tmp_path), capture_output=True, text=True, timeout=30
        )
        assert second.returncode == 0, second.stderr
        assert time.monotonic() - started < 20
        assert first.poll() is None  # a primeira continua aberta
    finally:
        first.terminate()
        first.wait(timeout=20)

    bad = subprocess.run(
        [*command, "--set", "workers=0"],
        env=_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert bad.returncode == 2
    assert "workers em argumento --set workers" in bad.stderr


# Tela de configurações -----------------------------------------------------------------


@pytest.fixture
def with_settings(tmp_path: Path, repo: Path) -> Iterator[tuple[TestClient, Path]]:
    from qa_engine.adapters.paths import AppPaths
    from qa_engine.adapters.settings import LayeredSettings

    paths = AppPaths(
        machine_config=tmp_path / "maquina" / "config.toml",
        user_config=tmp_path / "usuario" / "config.toml",
        data_dir=tmp_path / "data",
        output_dir=tmp_path / "Saída",
        program_dir=repo,
    )
    paths.machine_config.parent.mkdir()
    paths.machine_config.write_text('[locked]\nkeys = ["allowed_roots"]\n', "utf-8")
    source = LayeredSettings.for_desktop(paths, env={})
    settings = desktop_settings(base_settings(tmp_path, repo), 51234, "tk")
    app = create_app(settings, source)
    with TestClient(app, base_url="http://127.0.0.1:51234") as client:
        client.headers["Authorization"] = "Bearer tk"
        yield client, paths.user_config


def test_settings_view_shows_origin_and_locked_keys(
    with_settings: tuple[TestClient, Path],
) -> None:
    from qa_engine.application.contracts import validate

    client, _ = with_settings
    assert "settings" in client.get("/health").json()["capabilities"]
    view = client.get("/settings").json()
    validate(view, "settings-view.schema.json")
    assert view["origins"]["workers"] == "default"
    assert view["locked"] == ["allowed_roots"]
    assert "allowed_roots" not in view["editable"] and "output_dir" in view["editable"]
    assert view["values"]["api_token"] is None
    assert view["restart_required"] is False


def test_put_settings_refuses_invalid_values_before_writing(
    with_settings: tuple[TestClient, Path],
) -> None:
    client, user_file = with_settings
    r = client.put("/settings", json={"changes": {"workers": 0, "log_level": "verbose"}})
    assert r.status_code == 422
    problems = {p["key"]: p for p in r.json()["problems"]}
    assert set(problems) == {"workers", "log_level"}
    assert problems["workers"]["source"] == str(user_file) and problems["workers"]["value"] == 0
    assert not user_file.exists()

    locked = client.put("/settings", json={"changes": {"allowed_roots": ["C:/x"]}})
    assert locked.status_code == 422
    assert locked.json()["problems"][0]["key"] == "allowed_roots"
    token = client.put("/settings", json={"changes": {"api_token": "x"}})
    assert token.status_code == 422

    ok = client.put("/settings", json={"changes": {"workers": 2, "output_dir": "D:/Saída"}})
    assert ok.status_code == 200, ok.text
    assert ok.json()["origins"]["workers"] == "user" and ok.json()["restart_required"] is True
    reset = client.put("/settings", json={"reset": ["workers"]}).json()
    assert reset["origins"]["workers"] == "default"


def test_settings_only_where_there_is_a_source(tmp_path: Path, repo: Path) -> None:
    with TestClient(create_app(base_settings(tmp_path, repo))) as client:
        assert client.get("/settings").status_code == 404
        assert "settings" not in client.get("/health").json()["capabilities"]


def test_profile_rules_show_where_each_value_came_from(
    with_settings: tuple[TestClient, Path],
) -> None:
    from qa_engine.application.contracts import validate

    client, _ = with_settings
    rules = client.get("/profiles/sos-piloto/rules", params={"station_id": "cg-e3"}).json()
    validate(rules, "profile-rules.schema.json")
    borders = next(r for r in rules if r["rule"] == "black_borders")
    dark = next(p for p in borders["params"] if p["name"] == "dark_level")
    assert (dark["value"], dark["source"], dark["default"]) == (60, "station", 70)
    assert dark["type"] == "integer" and dark["minimum"] == 0
    assert client.get("/profiles/sos-piloto/rules", params={"station_id": "x"}).status_code == 404


def test_profile_params_out_of_range_are_refused(
    with_settings: tuple[TestClient, Path],
) -> None:
    client, _ = with_settings
    profile = client.get("/profiles/sos-piloto").json()
    profile["stations"][0]["overrides"]["black_borders"]["params"]["dark_level"] = -5
    r = client.put("/profiles/sos-piloto", json=profile)
    assert r.status_code == 422
    assert "black_borders.dark_level: esperado ≥ 0" in r.json()["title"] + r.json().get(
        "detail", ""
    )


def test_self_test_finds_the_known_defects(tmp_path: Path, repo: Path) -> None:
    import synth

    from qa_engine.application.profile import load_profile
    from qa_engine.application.selftest import compare_with_key, run_self_test

    sample = tmp_path / "lote-exemplo"
    synth.build(sample, synth.selftest_plan(), 20261105, (1240, 1748))
    result = run_self_test(sample, load_profile(repo / "profiles/completo.yaml"), workers=1)
    assert result.ok, result.errors
    assert result.pages == 7 and result.ms_per_page > 0

    key = json.loads((sample / "gabarito.json").read_text("utf-8"))
    key["defects"].append({"rule": "skew", "file": "CX001/DOC0002/0001.tif"})
    report = {"pages": [], "documents": [], "findings": []}
    assert "faltou skew em CX001/DOC0002/0001.tif" in compare_with_key(report, key)
    failing = run_self_test(
        sample,
        load_profile(repo / "profiles/completo.yaml"),
        workers=1,
        extra_checks={"interface": False},
    )
    assert not failing.ok and "conferência falhou: interface" in failing.errors
