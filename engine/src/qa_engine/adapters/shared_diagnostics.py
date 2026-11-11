"""Diagnóstico na pasta compartilhada (``diagnostics_dir``): um arquivo por computador.

Cada máquina acrescenta seus registros em ``<computador>.jsonl``; a tela de
Diagnóstico de qualquer máquina lê todos. Pasta fora do ar não derruba nada: o
registro fica no banco local e o erro de gravação vai só para o log.
"""

from __future__ import annotations

import json
import logging
import platform
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

log = logging.getLogger("qa_engine.diagnostics")


class SharedDiagnosticsFolder:
    """Lê e grava registros de diagnóstico numa pasta de rede."""

    def __init__(self, folder: Path, machine: str | None = None) -> None:
        self.folder = folder
        name = machine or platform.node() or "computador"
        self.file = folder / (re.sub(r"[^\w.-]", "_", name) + ".jsonl")

    def append(self, record: Mapping[str, Any]) -> None:
        """Acrescenta um registro; falha de rede vira só uma linha de log."""
        try:
            self.folder.mkdir(parents=True, exist_ok=True)
            with self.file.open("a", encoding="utf-8") as out:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
        except OSError as exc:
            log.warning("pasta de diagnóstico indisponível: %s", exc.strerror or exc)

    def read_all(self) -> list[dict[str, Any]]:
        """Registros de todas as máquinas; linhas ilegíveis são puladas."""
        records: list[dict[str, Any]] = []
        try:
            files = sorted(self.folder.glob("*.jsonl"))
        except OSError:
            return records
        for path in files:
            try:
                lines = path.read_text("utf-8").splitlines()
            except OSError:
                continue
            for line in lines:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return records
