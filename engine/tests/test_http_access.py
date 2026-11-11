"""Acesso pelo navegador: CORS em toda resposta, modo de acesso, demonstração e mesma origem.

Regressão do "Failed to fetch" no celular (ADR-0010): sem cabeçalho CORS numa
resposta de erro, ou com a origem configurada com barra no fim, o navegador
esconde a resposta e a interface só vê uma falha de rede.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from qa_engine.application.contracts import validate
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings, normalize_origin

UI_ORIGIN = "https://interface.exemplo"


def make_client(tmp_path: Path, full_profile_path: Path, **overrides: object) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data["resolution"] = {"min_dpi": 150}
    (profiles / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    options: dict[str, object] = {
        "data_dir": tmp_path / "data",
        "profiles_dir": profiles,
        "api_token": None,
        "cors_origins": (UI_ORIGIN + "/",),  # barra no fim, como copiada do navegador
        "retention_hours": 24,
        "max_upload_mb": 50,
        "workers": 1,
        **overrides,
    }
    return TestClient(create_app(Settings(**options)), raise_server_exceptions=False)  # type: ignore[arg-type]


@pytest.fixture
def open_client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path, full_profile_path) as c:
        yield c


@pytest.fixture
def token_client(tmp_path: Path, full_profile_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path, full_profile_path, api_token="segredo") as c:
        yield c


ORIGIN = {"Origin": UI_ORIGIN}


@pytest.mark.parametrize(
    ("raw", "origin"),
    [
        ("https://interface.exemplo/", UI_ORIGIN),
        ("  https://Interface.Exemplo  ", UI_ORIGIN),
        ("https://interface.exemplo/app/", UI_ORIGIN),
        ("http://localhost:5173", "http://localhost:5173"),
        ("*", "*"),
    ],
)
def test_normalize_origin(raw: str, origin: str) -> None:
    assert normalize_origin(raw) == origin


def test_cors_on_success_errors_and_preflight(token_client: TestClient) -> None:
    ok = token_client.get("/batches", headers={**ORIGIN, "Authorization": "Bearer segredo"})
    unauthorized = token_client.get("/batches", headers=ORIGIN)
    not_found = token_client.get(
        "/batches/00000000-0000-0000-0000-000000000000",
        headers={**ORIGIN, "Authorization": "Bearer segredo"},
    )
    preflight = token_client.options(
        "/batches",
        headers={
            **ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert (ok.status_code, unauthorized.status_code, not_found.status_code) == (200, 401, 404)
    for response in (ok, unauthorized, not_found, preflight):
        assert response.headers.get("access-control-allow-origin") == UI_ORIGIN
    assert unauthorized.json()["title"] == "Não autorizado"


def test_cors_on_unhandled_error(open_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    engine = open_client.app.state.engine  # type: ignore[attr-defined]

    def boom(*_: object) -> None:
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(engine.repo, "list_batches", boom)
    r = open_client.get("/batches", headers=ORIGIN)
    assert r.status_code == 500
    assert r.headers.get("access-control-allow-origin") == UI_ORIGIN
    assert r.headers["content-type"].startswith("application/problem+json")


def test_health_tells_the_interface_what_to_ask(
    open_client: TestClient, token_client: TestClient
) -> None:
    open_health = open_client.get("/health", headers=ORIGIN).json()
    token_health = token_client.get("/health", headers=ORIGIN).json()
    validate(open_health, "health.schema.json")
    assert open_health["auth_required"] is False
    assert token_health["auth_required"] is True  # token dormente: ligado pelo servidor
    assert open_client.get("/batches").status_code == 200  # demonstração: só o nome


def test_demo_batches(tmp_path: Path, full_profile_path: Path, small_batch: Path) -> None:
    demo_dir = tmp_path / "demo"
    demo_dir.mkdir()
    (demo_dir / "lote-demo").symlink_to(small_batch, target_is_directory=True)
    (small_batch / "gabarito.json").write_text("{}", encoding="utf-8")
    with make_client(tmp_path, full_profile_path, demo_dir=demo_dir) as c:
        listed = c.get("/demo-batches").json()
        for item in listed:
            validate(item, "demo-batch.schema.json")
        assert listed == [{"name": "lote-demo", "pages": 11, "documents": 2}]
        assert c.get("/health").json()["demo_batches"] == 1
        assert c.post("/demo-batches/../etc").status_code == 404
        assert c.post("/demo-batches/nao-existe").status_code == 404
        r = c.post("/demo-batches/lote-demo")
        assert r.status_code == 202, r.text
        batch_id = r.json()["id"]
        for _ in range(200):
            status = c.get(f"/batches/{batch_id}").json()
            if status["status"] != "queued" and status["status"] != "processing":
                break
            time.sleep(0.1)
        assert status["status"] == "analyzed"
        assert status["name"] == "lote-demo"
        copied = tmp_path / "data" / "batches" / batch_id / "input"
        assert not (copied / "gabarito.json").exists()  # a resposta não vai para o motor
        assert (small_batch / "gabarito.json").exists()  # o original da demonstração fica


def test_interface_on_same_origin(tmp_path: Path, full_profile_path: Path) -> None:
    ui = tmp_path / "ui"
    (ui / "assets").mkdir(parents=True)
    (ui / "index.html").write_text("<!doctype html><title>QA</title>", encoding="utf-8")
    (ui / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    with make_client(tmp_path, full_profile_path, ui_dir=ui, api_token="segredo") as c:
        index = c.get("/")
        assert index.status_code == 200
        assert "<title>QA</title>" in index.text
        assert c.get("/assets/app.js").status_code == 200
        assert c.get("/health").status_code == 200
        assert c.get("/batches").status_code == 401  # a API continua protegida
        assert c.get("/batches", headers={"Authorization": "Bearer segredo"}).status_code == 200


def test_port_follows_the_hosting_platform() -> None:
    from qa_engine.entrypoints.http.__main__ import port_from_env

    assert port_from_env({}) == 8000
    assert port_from_env({"PORT": "10000"}) == 10000  # Render define PORT
    assert port_from_env({"PORT": "10000", "QA_PORT": "9000"}) == 9000


@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("cloud", ["upload", "synthetic_only"]),
        ("desktop", ["local_batches", "folder_export", "os_session"]),
        ("server", ["upload", "folder_export"]),
    ],
)
def test_health_declares_mode_and_capabilities(
    tmp_path: Path, full_profile_path: Path, mode: str, expected: list[str]
) -> None:
    with make_client(tmp_path, full_profile_path, mode=mode) as c:
        health = c.get("/health").json()
        validate(health, "health.schema.json")
        assert health["mode"] == mode
        assert health["capabilities"] == expected
        session = c.get("/session").json()
        validate(session, "session.schema.json")
        if mode == "desktop":
            assert session["source"] == "os" and session["reviewer"]
        else:
            assert session == {"reviewer": None, "machine": None, "source": "none"}


def test_session_requires_the_token(tmp_path: Path, full_profile_path: Path) -> None:
    with make_client(tmp_path, full_profile_path, mode="desktop", api_token="t") as c:
        assert c.get("/session").status_code == 401
        assert c.get("/session", headers={"Authorization": "Bearer t"}).status_code == 200
        assert c.post("/local-batches", json={"path": "x"}).status_code == 401
