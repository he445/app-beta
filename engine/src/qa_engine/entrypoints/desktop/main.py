"""Abertura do programa desktop.

1. configuração em camadas (erro → tela de erro e fim);
2. uma instância por usuário (segunda abertura traz a janela existente);
3. porta livre em 127.0.0.1 e token novo a cada abertura;
4. uvicorn numa thread, servindo a API e a interface na mesma origem;
5. espera ``/health`` e abre a janela (pywebview, WebView2). Sem WebView2, abre o
   navegador padrão com um código de uso único no fragmento da URL;
6. ao fechar a janela, encerra o motor (filas, processos de análise, banco).
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import html
import json
import logging
import secrets
import socket
import sys
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import uvicorn

from qa_engine import __version__
from qa_engine.adapters.instance import InstanceLock
from qa_engine.adapters.logs import setup_file_logging, write_crash
from qa_engine.adapters.paths import AppPaths
from qa_engine.adapters.settings import LayeredSettings, parse_overrides
from qa_engine.application.settings import Settings, SettingsError
from qa_engine.ports import SettingsSource

log = logging.getLogger("qa_engine.desktop")
HOST = "127.0.0.1"
TITLE = "QA de Digitalização"
STARTUP_TIMEOUT = 60.0
BROWSER_IDLE_HOURS = 8.0
"""No plano B pelo navegador, o motor se encerra depois de tanto tempo sem uso."""


def free_port(host: str = HOST) -> int:
    """Porta livre que o sistema escolheu (nunca fixa: duas contas na mesma máquina)."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        port: int = sock.getsockname()[1]
        return port


def desktop_settings(base: Settings, port: int, token: str) -> Settings:
    """Configuração efetiva do desktop: só 127.0.0.1, token desta abertura, sem CORS."""
    return dataclasses.replace(
        base,
        mode="desktop",
        api_token=token,
        cors_origins=(),
        trusted_hosts=(f"{HOST}:{port}", f"localhost:{port}"),
    )


def wait_healthy(url: str, timeout: float = STARTUP_TIMEOUT) -> None:
    """Espera ``GET /health`` responder.

    Raises:
        TimeoutError: o motor não respondeu a tempo.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/health", timeout=2) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(0.2)
    raise TimeoutError("o motor não respondeu ao abrir")


def ask_existing_to_focus(owner: dict[str, Any]) -> bool:
    """Pede à instância aberta que traga a janela para a frente."""
    request = urllib.request.Request(
        f"http://{HOST}:{owner['port']}/desktop/focus",
        method="POST",
        headers={
            "X-Instance-Secret": str(owner.get("secret", "")),
            "Host": f"{HOST}:{owner['port']}",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return bool(response.status == 204)
    except (urllib.error.URLError, OSError):
        return False


class Bridge:
    """O que a janela expõe à interface em ``window.pywebview.api``.

    O token vai pela ponte, nunca pela URL: assim não aparece em histórico nem em log.
    """

    def __init__(self, token: str) -> None:
        self._token = token
        self.window: Any = None

    def get_session(self) -> dict[str, str]:
        """Token desta abertura."""
        return {"token": self._token}

    def pick_folder(self) -> str | None:
        """Diálogo nativo de escolher pasta; ``None`` se a pessoa cancelar."""
        if self.window is None:
            return None
        import webview

        chosen = self.window.create_file_dialog(webview.FileDialog.FOLDER)
        return str(chosen[0]) if chosen else None


class EngineServer:
    """uvicorn numa thread, com encerramento limpo."""

    def __init__(self, settings: Settings, port: int, source: SettingsSource | None = None) -> None:
        from qa_engine.entrypoints.http.app import create_app

        self.app = create_app(settings, source)
        self.url = f"http://{HOST}:{port}"
        config = uvicorn.Config(self.app, host=HOST, port=port, log_config=None, access_log=False)
        self.server = uvicorn.Server(config)
        self.thread = threading.Thread(target=self.server.run, name="motor", daemon=True)

    def start(self) -> None:
        """Sobe e espera ``/health``."""
        self.thread.start()
        wait_healthy(self.url)

    def stop(self, timeout: float = 15.0) -> None:
        """Pede o encerramento e espera o motor fechar filas e banco."""
        self.server.should_exit = True
        self.thread.join(timeout)

    def last_request_age(self) -> float:
        """Segundos desde a última requisição (plano B pelo navegador)."""
        engine = self.app.state.engine
        return time.monotonic() - float(getattr(engine, "last_request", time.monotonic()))


def error_page(problems: Sequence[str], hint: str) -> str:
    """Tela de erro da abertura, em HTML simples, para a janela ou o navegador."""
    items = "".join(f"<li><code>{html.escape(p)}</code></li>" for p in problems)
    return (
        "<!doctype html><meta charset=utf-8><title>QA de Digitalização</title>"
        "<body style='font-family:Segoe UI,system-ui,sans-serif;margin:2rem;max-width:48rem'>"
        "<h1>O programa não pôde abrir</h1>"
        f"<p>{html.escape(hint)}</p><ul>{items}</ul>"
        f"<p style='color:#555'>QA {__version__}</p></body>"
    )


def show_error(problems: Sequence[str], hint: str, headless: bool) -> None:
    """Mostra o erro numa janela; sem janela, na saída de erro."""
    if sys.stderr is not None:
        print(hint, *problems, sep="\n", file=sys.stderr)
    if headless:
        return
    try:
        import webview

        webview.create_window(TITLE, html=error_page(problems, hint), width=720, height=480)
        webview.start()
    except Exception:
        log.exception("não foi possível mostrar a tela de erro")


def build_parser() -> argparse.ArgumentParser:
    """Argumentos para suporte e testes."""
    parser = argparse.ArgumentParser(
        prog="QA", description="QA de Digitalização (programa desktop)"
    )
    parser.add_argument("--version", action="version", version=f"QA {__version__}")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="CHAVE=VALOR",
        help="sobrescreve uma chave da configuração (camada mais forte)",
    )
    parser.add_argument("--headless", action="store_true", help="sem janela: só o motor")
    parser.add_argument("--browser", action="store_true", help="abrir no navegador padrão")
    parser.add_argument("--port", type=int, default=0, help="porta fixa (padrão: livre)")
    parser.add_argument(
        "--self-test",
        nargs="?",
        const="",
        metavar="PASTA",
        help="analisa o lote de exemplo do pacote (ou PASTA, com gabarito.json) e sai",
    )
    parser.add_argument("--budget-ms", type=float, default=1000.0, help="orçamento por página")
    return parser


def say(*parts: object) -> None:
    """Escreve na saída padrão, se houver (no executável com janela ela não existe)."""
    if sys.stdout is not None:
        print(*parts, flush=True)


def self_test(folder: str, budget_ms: float) -> int:
    """Teste de fumaça do pacote: código 0 se tudo conferiu."""
    from qa_engine.application.models import verify_models
    from qa_engine.application.profile import load_profile
    from qa_engine.application.selftest import run_self_test

    program = AppPaths.detect().program_dir
    sample = Path(folder) if folder else program / "samples" / "lote-exemplo"
    ui = program / "ui" if getattr(sys, "frozen", False) else program / "ui" / "dist"
    models = verify_models(program / "models")
    checks = {
        "modelos": models.ok,
        "interface": (ui / "index.html").is_file(),
        "perfis": (program / "profiles" / "sos-piloto.yaml").is_file(),
        "lote de exemplo": (sample / "gabarito.json").is_file(),
    }
    if not checks["lote de exemplo"]:
        say(json.dumps({"ok": False, "checks": checks}, ensure_ascii=False))
        return 1
    result = run_self_test(
        sample,
        load_profile(program / "profiles" / "completo.yaml"),
        budget_ms=budget_ms,
        extra_checks=checks,
        models_dir=program / "models" if models.ok else None,
    )
    payload = result.json()
    if models.problems:
        payload["errors"] = [*payload["errors"], *models.problems]
    say(json.dumps(payload, ensure_ascii=False))
    return 0 if result.ok else 1


def open_window(server: EngineServer, bridge: Bridge, on_closed: Callable[[], None]) -> bool:
    """Abre a janela pywebview; falso se não houver WebView2 (ou outro motor de janela)."""
    try:
        import webview
    except ImportError:
        return False
    try:
        window = webview.create_window(
            TITLE, server.url, js_api=bridge, width=1366, height=860, min_size=(900, 600)
        )
        if window is None:
            return False
        bridge.window = window

        def focus() -> None:
            window.restore()
            window.show()

        server.app.state.focus_handler = focus
        window.events.closed += on_closed
        webview.start(private_mode=False)
    except Exception:
        log.exception("janela indisponível; abrindo no navegador")
        return False
    return True


def open_browser(server: EngineServer) -> None:
    """Plano B: navegador padrão com código de uso único no fragmento da URL."""
    engine = server.app.state.engine

    def reopen() -> None:
        webbrowser.open(f"{server.url}/#code={engine.issue_code()}")

    server.app.state.focus_handler = reopen
    reopen()
    while server.thread.is_alive() and server.last_request_age() < BROWSER_IDLE_HOURS * 3600:
        time.sleep(5)


CLI_COMMANDS = frozenset(
    {"admin", "beta", "feedback", "rules", "validate-profile", "validate-report"}
)
"""Subcomandos da linha de comando ``qa`` que o executável de suporte também atende."""


def main(argv: Sequence[str] | None = None) -> int:
    """Abre o programa. Código de saída 0 ao fechar; 2 se a configuração for inválida."""
    given = list(sys.argv[1:] if argv is None else argv)
    if given and given[0] in CLI_COMMANDS:
        # QA-suporte.exe beta report, QA-suporte.exe admin token...: a mesma linha de comando
        # do motor, sem precisar do código-fonte na estação.
        from qa_engine.entrypoints.cli.main import main as cli

        return cli(given)
    args = build_parser().parse_args(argv)
    if args.self_test is not None:
        return self_test(args.self_test, args.budget_ms)
    paths = AppPaths.detect()
    try:
        source = LayeredSettings.for_desktop(paths, args=parse_overrides(args.set))
        resolved = source.load()
    except SettingsError as exc:
        show_error(
            [str(p) for p in exc.problems],
            "A configuração tem valores inválidos. Corrija o arquivo indicado ou fale com a TI.",
            args.headless,
        )
        return 2

    base = resolved.settings
    setup_file_logging(base.data_dir / "logs", base.log_level)
    lock = InstanceLock(base.data_dir)
    if not lock.acquire():
        owner = lock.owner()
        if owner and ask_existing_to_focus(owner):
            return 0
        show_error(
            [str(lock.path)],
            "O programa já está aberto nesta conta, mas não respondeu. Feche-o e abra de novo.",
            args.headless,
        )
        return 3

    try:
        port = args.port or free_port()
        token = secrets.token_urlsafe(32)
        server = EngineServer(desktop_settings(base, port, token), port, source)
        server.app.state.focus_secret = secrets.token_urlsafe(16)
        server.start()
        lock.publish(port, server.app.state.focus_secret)
        log.info("programa aberto na porta %s (versão %s)", port, __version__)
        if args.headless:
            say(f"motor em {server.url}")
            # Para suporte: abre a interface num navegador desta máquina, uma vez.
            code = server.app.state.engine.issue_code()
            say(f"acesso: {server.url}/#code={code}")
            with contextlib.suppress(KeyboardInterrupt):
                server.thread.join()
        elif args.browser or not open_window(server, Bridge(token), server.stop):
            open_browser(server)
        server.stop()
        return 0
    except Exception as exc:
        crash = write_crash(base.data_dir / "logs", exc, __version__)
        show_error([str(exc), f"Detalhes em {crash}"], "Erro ao abrir o programa.", args.headless)
        return 1
    finally:
        lock.release()
