"""Histórico de configuração: cada mudança vira uma linha com o antes e o depois.

As chaves são caminhos com pontos (``stations.cg-e3.rules.blur.params.dark_level``);
listas são comparadas inteiras. Entra na tela de Configurações e no resumo de
configuração gravado com cada lote.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def flatten(data: Any, prefix: str = "") -> dict[str, Any]:
    """Folhas de um dicionário aninhado, com o caminho em pontos."""
    if isinstance(data, Mapping):
        out: dict[str, Any] = {}
        for key, value in data.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            out.update(flatten(value, path))
        return out
    if isinstance(data, list) and data and all(isinstance(i, Mapping) and "id" in i for i in data):
        # Listas de itens com id (estações): compara item a item pelo id.
        return flatten({str(item["id"]): item for item in data}, prefix)
    return {prefix: data}


def changes(before: Any, after: Any) -> list[tuple[str, Any, Any]]:
    """O que mudou de ``before`` para ``after``: (chave, valor anterior, valor novo)."""
    old, new = flatten(before), flatten(after)
    return [
        (key, old.get(key), new.get(key))
        for key in sorted(set(old) | set(new))
        if old.get(key) != new.get(key)
    ]
