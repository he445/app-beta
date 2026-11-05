"""Identificadores determinísticos (seção 16, item 4: determinismo).

A mesma entrada gera os mesmos identificadores em qualquer máquina, o que
permite comparar execuções e implementações em linguagens diferentes.
"""

from __future__ import annotations

import uuid

NAMESPACE = uuid.UUID("6f1c2b8e-4a77-5d0e-9c3a-2f3b9d1e7a10")


def batch_id(content_key: str) -> str:
    """Identificador do lote a partir de uma chave de conteúdo (ex.: hash dos arquivos)."""
    return str(uuid.uuid5(NAMESPACE, f"batch/{content_key}"))


def document_id(batch: str, name: str) -> str:
    """Identificador de um documento dentro do lote."""
    return str(uuid.uuid5(uuid.UUID(batch), f"document/{name}"))


def page_id(batch: str, source_file: str, page_in_file: int) -> str:
    """Identificador de uma página pelo arquivo de origem e posição no arquivo."""
    return str(uuid.uuid5(uuid.UUID(batch), f"page/{source_file}#{page_in_file}"))


def finding_id(batch: str, target_id: str, rule: str, ordinal: int = 0) -> str:
    """Identificador de uma sinalização: alvo, regra e ordinal."""
    return str(uuid.uuid5(uuid.UUID(batch), f"finding/{target_id}/{rule}/{ordinal}"))
