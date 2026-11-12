"""Relatórios por caixa na pasta compartilhada (``reports_dir``): um JSON por versão.

A mesma pasta guarda, em ``maquinas/``, a versão do programa e a última abertura de cada
máquina (para a Gestão achar estação esquecida numa versão antiga), e em ``travas/`` as
travas das caixas em conferência.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

MACHINES_FOLDER = "maquinas"


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
            if path.relative_to(self.root).parts[0] in {MACHINES_FOLDER, "travas"}:
                continue
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

    def write_machine(self, info: Mapping[str, Any]) -> None:
        """Grava a versão e a última abertura desta máquina (temporário renomeado).

        Raises:
            OSError: a pasta compartilhada não está acessível.
        """
        folder = self.root / MACHINES_FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        name = re.sub(r'[\\/:*?"<>|]', "_", str(info["machine"])).strip(" .") or "maquina"
        target = folder / f"{name}.json"
        part = target.with_name(target.name + ".part")
        part.write_text(json.dumps(dict(info), ensure_ascii=False), encoding="utf-8")
        part.replace(target)

    def machines(self) -> list[dict[str, Any]]:
        """Versão e última abertura de cada máquina (arquivos ilegíveis são pulados)."""
        folder = self.root / MACHINES_FOLDER
        found: list[dict[str, Any]] = []
        try:
            paths = sorted(folder.glob("*.json")) if folder.is_dir() else []
        except OSError:
            return found
        for path in paths:
            try:
                data = json.loads(path.read_text("utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and {"machine", "program_version", "last_seen_at"} <= set(
                data
            ):
                found.append(data)
        return found
