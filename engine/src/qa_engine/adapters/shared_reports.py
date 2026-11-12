"""Relatórios por caixa na pasta compartilhada (``reports_dir``): um JSON por versão."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any


class SharedReportsFolder:
    """Lê os relatórios de todas as máquinas gravados em ``reports_dir``."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def read(self, valid: Callable[[Any], bool]) -> tuple[list[tuple[str, dict[str, Any]]], int]:
        """Relatórios válidos (caminho relativo, conteúdo) e quantos arquivos foram pulados.

        Arquivo ilegível, incompleto (cópia em andamento) ou fora do contrato é pulado:
        uma máquina com problema não derruba a tela de Gestão.
        """
        found: list[tuple[str, dict[str, Any]]] = []
        skipped = 0
        if not self.root.is_dir():
            return found, skipped
        for path in sorted(self.root.rglob("*.json")):
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                skipped += 1
                continue
            if not valid(data):
                skipped += 1
                continue
            found.append((path.relative_to(self.root).as_posix(), data))
        return found, skipped

    def resolve(self, rel: str) -> Path | None:
        """Caminho de um relatório pela referência, sem sair da pasta compartilhada."""
        candidate = (self.root / rel).resolve()
        root = self.root.resolve()
        if candidate.suffix != ".json" or root not in candidate.parents or not candidate.is_file():
            return None
        return candidate
