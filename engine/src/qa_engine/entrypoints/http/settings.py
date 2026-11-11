"""Configuração da API: :class:`Settings` resolvida pelas camadas (ADR-0012)."""

from __future__ import annotations

from urllib.parse import urlsplit

from qa_engine.application.settings import Settings

__all__ = ["Settings", "normalize_origin", "server_settings"]


def server_settings() -> Settings:
    """Configuração do motor em servidor: padrões embutidos mais as variáveis ``QA_*``."""
    from qa_engine.adapters.settings import LayeredSettings

    return LayeredSettings.for_server().load().settings


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
