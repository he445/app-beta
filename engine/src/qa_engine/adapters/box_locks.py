"""Trava por caixa: um arquivo ``<caixa>.lock`` na pasta compartilhada (ou só nesta máquina).

Dois conferentes não podem conferir a mesma caixa em máquinas diferentes. A pasta
original é só leitura, então a trava fica em ``reports_dir/travas``; sem pasta
compartilhada, em ``data_dir/travas`` (vale só dentro da máquina).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

STALE_SECONDS = 600
"""Trava sem renovação há mais que isso é considerada abandonada e pode ser assumida."""


class BoxLockedError(Exception):
    """A caixa está em conferência por outra pessoa."""

    def __init__(self, lock: dict[str, Any], stale: bool) -> None:
        super().__init__(lock.get("box", ""))
        self.lock = lock
        self.stale = stale


def _safe(box: str) -> str:
    cleaned = "".join("_" if ch in '\\/:*?"<>|' or ord(ch) < 32 else ch for ch in box)
    return cleaned.strip(" .") or "sem-nome"


class BoxLocks:
    """Travas de caixa numa pasta (compartilhada ou local)."""

    def __init__(self, folder: Path, shared: bool) -> None:
        self.folder = folder
        self.shared = shared

    def _path(self, box: str) -> Path:
        return self.folder / f"{_safe(box)}.lock"

    def read(self, box: str) -> dict[str, Any] | None:
        """A trava da caixa, se houver (arquivo ilegível conta como sem trava)."""
        try:
            data: dict[str, Any] = json.loads(self._path(box).read_text("utf-8"))
        except (OSError, ValueError):
            return None
        return data

    @staticmethod
    def is_stale(lock: dict[str, Any], now: datetime) -> bool:
        """Sem renovação há mais de :data:`STALE_SECONDS`."""
        try:
            renewed = datetime.fromisoformat(str(lock["renewed_at"]))
        except (KeyError, ValueError):
            return True
        return (now - renewed).total_seconds() > STALE_SECONDS

    def _write(self, box: str, data: dict[str, Any], exclusive: bool) -> bool:
        self.folder.mkdir(parents=True, exist_ok=True)
        text = json.dumps(data, ensure_ascii=False, indent=2)
        if exclusive:
            try:
                with open(self._path(box), "x", encoding="utf-8") as handle:
                    handle.write(text)
            except FileExistsError:
                return False
            return True
        part = self.folder / f".{_safe(box)}.{uuid.uuid4().hex}.part"
        part.write_text(text, "utf-8")
        os.replace(part, self._path(box))
        return True

    def acquire(
        self,
        box: str,
        holder: dict[str, Any],
        now: datetime,
        take_over: bool = False,
    ) -> dict[str, Any]:
        """Trava a caixa para ``holder`` (``id``, ``reviewer``, ``machine``).

        Raises:
            BoxLockedError: a caixa está travada por outra pessoa (``stale`` diz se a
                trava foi abandonada e pode ser assumida com ``take_over``).
        """
        at = now.isoformat(timespec="seconds")
        data = {"box": box, **holder, "acquired_at": at, "renewed_at": at}
        current = self.read(box)
        if current is not None and current.get("id") == holder["id"]:
            return self.renew(box, holder["id"], now) or data
        if current is None and self._write(box, data, exclusive=True):
            return data
        current = self.read(box) or {}
        stale = self.is_stale(current, now)
        if not (stale and take_over):
            raise BoxLockedError(current, stale)
        data["taken_over_from"] = {
            k: current.get(k) for k in ("reviewer", "machine", "acquired_at", "renewed_at")
        }
        self._write(box, data, exclusive=False)
        return data

    def renew(self, box: str, holder_id: str, now: datetime) -> dict[str, Any] | None:
        """Renova a trava; ``None`` se ela não é mais de ``holder_id`` (alguém assumiu)."""
        current = self.read(box)
        if current is None or current.get("id") != holder_id:
            return None
        current["renewed_at"] = now.isoformat(timespec="seconds")
        self._write(box, current, exclusive=False)
        return current

    def release(self, box: str, holder_id: str) -> bool:
        """Solta a trava se ela for de ``holder_id``."""
        current = self.read(box)
        if current is None or current.get("id") != holder_id:
            return False
        self._path(box).unlink(missing_ok=True)
        return True
