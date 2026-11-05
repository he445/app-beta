"""``python -m qa_engine.entrypoints.http``: sobe a API com uvicorn."""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    """Sobe o servidor em ``QA_HOST``:``QA_PORT`` (padrão 0.0.0.0:8000)."""
    uvicorn.run(
        "qa_engine.entrypoints.http.app:create_app",
        factory=True,
        host=os.environ.get("QA_HOST", "0.0.0.0"),
        port=int(os.environ.get("QA_PORT", "8000")),
    )


if __name__ == "__main__":
    main()
