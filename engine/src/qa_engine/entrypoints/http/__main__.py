"""``python -m qa_engine.entrypoints.http``: sobe a API com uvicorn."""

from __future__ import annotations

import os

import uvicorn


def port_from_env(env: dict[str, str] | None = None) -> int:
    """Porta: ``QA_PORT``; senão ``PORT`` (Render, Fly.io, Cloud Run); senão 8000."""
    env = dict(os.environ) if env is None else env
    return int(env.get("QA_PORT") or env.get("PORT") or "8000")


def main() -> None:
    """Sobe o servidor em ``QA_HOST`` (padrão 0.0.0.0) e na porta de :func:`port_from_env`."""
    uvicorn.run(
        "qa_engine.entrypoints.http.app:create_app",
        factory=True,
        host=os.environ.get("QA_HOST", "0.0.0.0"),
        port=port_from_env(),
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
