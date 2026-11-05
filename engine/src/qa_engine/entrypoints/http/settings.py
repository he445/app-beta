"""Configuração da API por variáveis de ambiente."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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
    """

    data_dir: Path
    profiles_dir: Path
    api_token: str | None
    cors_origins: tuple[str, ...]
    retention_hours: float
    max_upload_mb: int
    workers: int | None

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
            cors_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
            retention_hours=float(os.environ.get("QA_RETENTION_HOURS", "24")),
            max_upload_mb=int(os.environ.get("QA_MAX_UPLOAD_MB", "2048")),
            workers=int(workers) if workers else None,
        )
