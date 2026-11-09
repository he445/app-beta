"""Configuração da API por variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit


def normalize_origin(value: str) -> str:
    """Reduz um endereço à origem que o navegador envia (``esquema://host[:porta]``).

    Uma barra no fim (``https://ui.exemplo/``), copiada da barra de endereços,
    faria o navegador bloquear todas as respostas com "Failed to fetch".
    """
    value = value.strip()
    if value == "*":
        return value
    parts = urlsplit(value)
    if parts.scheme and parts.netloc:
        return f"{parts.scheme}://{parts.netloc}".lower()
    return value.rstrip("/").lower()


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração do serviço.

    Attributes:
        data_dir: onde ficam os lotes enviados e o banco SQLite (``QA_DATA_DIR``).
        profiles_dir: perfis YAML (``QA_PROFILES_DIR``).
        api_token: token exigido em ``Authorization: Bearer`` (``QA_API_TOKEN``);
            vazio desliga a autenticação, só para desenvolvimento local.
        cors_origins: domínios da interface aceitos (``QA_CORS_ORIGINS``, separados por vírgula).
        retention_hours: lotes são apagados depois disso (``QA_RETENTION_HOURS``, padrão 24).
        max_upload_mb: limite do envio (``QA_MAX_UPLOAD_MB``).
        workers: processos de análise (``QA_WORKERS``; vazio = todos os núcleos).
            Em servidor pequeno (512 MB), use 1: cada processo carrega OpenCV e NumPy.
        demo_dir: lotes de demonstração prontos no servidor (``QA_DEMO_DIR``).
        ui_dir: interface compilada para servir na mesma origem (``QA_UI_DIR``).
    """

    data_dir: Path
    profiles_dir: Path
    api_token: str | None
    cors_origins: tuple[str, ...]
    retention_hours: float
    max_upload_mb: int
    workers: int | None
    demo_dir: Path | None = None
    ui_dir: Path | None = None

    @classmethod
    def from_env(cls) -> Settings:
        """Lê as variáveis ``QA_*``."""
        default_profiles = Path(__file__).resolve().parents[5] / "profiles"
        workers = os.environ.get("QA_WORKERS")
        origins = os.environ.get("QA_CORS_ORIGINS", "")
        return cls(
            data_dir=Path(os.environ.get("QA_DATA_DIR", "./data")),
            profiles_dir=Path(os.environ.get("QA_PROFILES_DIR", str(default_profiles))),
            api_token=os.environ.get("QA_API_TOKEN") or None,
            cors_origins=tuple(normalize_origin(o) for o in origins.split(",") if o.strip()),
            retention_hours=float(os.environ.get("QA_RETENTION_HOURS", "24")),
            max_upload_mb=int(os.environ.get("QA_MAX_UPLOAD_MB", "2048")),
            workers=int(workers) if workers else None,
            demo_dir=Path(os.environ["QA_DEMO_DIR"]) if os.environ.get("QA_DEMO_DIR") else None,
            ui_dir=Path(os.environ["QA_UI_DIR"]) if os.environ.get("QA_UI_DIR") else None,
        )
