"""``PageVersionStore`` em disco: ``<lote>/corrected/`` com PNG e ``corrections.jsonl``."""

from __future__ import annotations

import hashlib
import json
import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

LOG_NAME = "corrections.jsonl"
_LOCKS: dict[Path, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _lock_for(folder: Path) -> threading.Lock:
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(folder.resolve(), threading.Lock())


class FilePageVersionStore:
    """Versões corrigidas das páginas de um lote.

    O log é só de inserção: cada linha diz qual cadeia de correções gerou qual
    arquivo. As cópias nunca sobrescrevem o original nem umas às outras.
    """

    def __init__(self, folder: Path) -> None:
        self.folder = folder
        self._lock = _lock_for(folder)

    def events(self) -> list[dict[str, Any]]:
        """Eventos válidos do log (linhas antigas sem ``seq`` são ignoradas)."""
        path = self.folder / LOG_NAME
        if not path.is_file():
            return []
        with self._lock:
            lines = path.read_text("utf-8").splitlines()
        events = []
        for line in lines:
            if not line.strip():
                continue
            data = json.loads(line)
            if "seq" in data and "chain" in data:
                events.append(data)
        return events

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Grava o evento com o próximo ``seq``."""
        self.folder.mkdir(parents=True, exist_ok=True)
        with self._lock:
            path = self.folder / LOG_NAME
            seq = 1
            if path.is_file():
                seq = sum(1 for line in path.read_text("utf-8").splitlines() if line.strip()) + 1
            stored = {"seq": seq, **event}
            with path.open("a", encoding="utf-8") as log:
                log.write(json.dumps(stored, ensure_ascii=False) + "\n")
        return stored

    def save(self, page_id: str, image: NDArray[np.uint8], dpi: float | None) -> tuple[str, str]:
        """Grava ``<page_id>.<n>.png`` (sem perda, com o DPI do original)."""
        self.folder.mkdir(parents=True, exist_ok=True)
        with self._lock:
            n = len(list(self.folder.glob(f"{page_id}.*.png"))) + 1
            name = f"{page_id}.{n:04d}.png"
            path = self.folder / name
            Image.fromarray(image).save(path, dpi=(dpi, dpi) if dpi else None, compress_level=1)
        return name, hashlib.sha256(path.read_bytes()).hexdigest()

    def load(self, name: str) -> NDArray[np.uint8] | None:
        """Lê a versão ``name``."""
        path = self.folder / Path(name).name
        if not path.is_file():
            return None
        with Image.open(path) as img:
            return np.asarray(img)
