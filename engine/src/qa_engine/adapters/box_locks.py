"""Travas por caixa numa pasta: um arquivo ``<caixa>.lock`` por caixa em conferência.

Com ``reports_dir`` configurado, a pasta é ``<reports_dir>/travas`` e vale para todas as
máquinas; sem ela, ``<data_dir>/travas`` e vale só neste computador. Criar usa abertura
exclusiva (o compartilhamento do Windows recusa a segunda criação); renovar e assumir
gravam num temporário e renomeiam, para ninguém ler uma trava pela metade.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from qa_engine.ports import BoxLock

LOCKS_FOLDER = "travas"
HISTORY_FILE = "historico.jsonl"


def lock_file_name(box: str) -> str:
    """Nome de arquivo seguro no Windows para a trava de uma caixa."""
    cleaned = "".join("_" if ch in '\\/:*?"<>|' or ord(ch) < 32 else ch for ch in box)
    return (cleaned.strip(" .") or "sem-nome") + ".lock"


def _from_json(data: Mapping[str, Any]) -> BoxLock:
    return BoxLock(
        box=str(data["box"]),
        reviewer=str(data["reviewer"]),
        machine=str(data["machine"]),
        since=str(data["since"]),
        renewed_at=str(data["renewed_at"]),
        batch_id=str(data.get("batch_id", "")),
        program_version=str(data.get("program_version", "")),
        taken_over_from=data.get("taken_over_from"),
    )


def lock_json(lock: BoxLock) -> dict[str, Any]:
    """Conteúdo do arquivo de trava (``box-lock.schema.json`` sem os campos calculados)."""
    data = asdict(lock)
    if data["taken_over_from"] is None:
        del data["taken_over_from"]
    else:
        data["taken_over_from"] = dict(data["taken_over_from"])
    return data


class FolderBoxLocks:
    """Porta ``BoxLockStore`` numa pasta local ou de rede."""

    def __init__(self, folder: Path, shared: bool) -> None:
        self.folder = folder
        self.shared = shared

    def _path(self, box: str) -> Path:
        return self.folder / lock_file_name(box)

    def read(self, box: str) -> BoxLock | None:
        """Trava atual; arquivo corrompido ou de outra versão conta como sem trava."""
        self.folder.mkdir(parents=True, exist_ok=True)
        try:
            text = self._path(box).read_text("utf-8")
        except FileNotFoundError:
            return None
        try:
            return _from_json(json.loads(text))
        except (ValueError, KeyError, TypeError):
            return None

    def create(self, lock: BoxLock) -> bool:
        """Cria só se não existir (abertura exclusiva)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        data = json.dumps(lock_json(lock), ensure_ascii=False).encode("utf-8")
        try:
            fd = os.open(self._path(lock.box), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
        except FileExistsError:
            return False
        with os.fdopen(fd, "wb") as out:
            out.write(data)
        return True

    def write(self, lock: BoxLock) -> None:
        """Grava por cima, num temporário renomeado no fim."""
        self.folder.mkdir(parents=True, exist_ok=True)
        target = self._path(lock.box)
        part = target.with_name(f"{target.name}.{os.getpid()}.part")
        part.write_text(json.dumps(lock_json(lock), ensure_ascii=False), encoding="utf-8")
        part.replace(target)

    def remove(self, box: str) -> None:
        """Apaga a trava; já apagada não é erro."""
        self._path(box).unlink(missing_ok=True)

    def log(self, event: Mapping[str, Any]) -> None:
        """Acrescenta uma linha ao histórico da pasta."""
        self.folder.mkdir(parents=True, exist_ok=True)
        with (self.folder / HISTORY_FILE).open("a", encoding="utf-8") as out:
            out.write(json.dumps(dict(event), ensure_ascii=False) + "\n")
