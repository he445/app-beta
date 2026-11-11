"""Uma instância do programa por usuário: trava de arquivo em ``data_dir``.

A primeira abertura trava ``instance.lock`` e grava nele a porta e um segredo.
A segunda não consegue a trava, lê a porta e pede à primeira que traga a janela
para a frente (``POST /desktop/focus`` com o segredo); depois termina.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import TracebackType
from typing import IO, Any

LOCK_FILE = "instance.lock"


def _try_lock(handle: IO[str]) -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt

            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


class InstanceLock:
    """Trava exclusiva enquanto o programa está aberto."""

    def __init__(self, folder: Path) -> None:
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / LOCK_FILE
        self._handle: IO[str] | None = None

    def acquire(self) -> bool:
        """Tenta travar; falso se outra instância já está aberta."""
        handle = self.path.open("a+", encoding="utf-8")
        if not _try_lock(handle):
            handle.close()
            return False
        self._handle = handle
        return True

    def publish(self, port: int, secret: str) -> None:
        """Grava a porta e o segredo para a próxima abertura encontrar esta instância."""
        assert self._handle is not None, "acquire() antes de publish()"
        # No Windows o primeiro byte fica travado: o conteúdo vai depois dele.
        self._handle.seek(0)
        self._handle.truncate()
        self._handle.write(" " + json.dumps({"port": port, "secret": secret, "pid": os.getpid()}))
        self._handle.flush()

    def owner(self) -> dict[str, Any] | None:
        """Porta, segredo e processo da instância aberta, se o arquivo tiver."""
        try:
            text = self.path.read_text("utf-8").strip()
        except OSError:
            return None
        try:
            data: dict[str, Any] = json.loads(text)
        except json.JSONDecodeError:
            return None
        return data

    def release(self) -> None:
        """Solta a trava (também acontece sozinho quando o processo termina)."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None

    def __enter__(self) -> InstanceLock:
        return self

    def __exit__(
        self,
        kind: type[BaseException] | None,
        error: BaseException | None,
        trace: TracebackType | None,
    ) -> None:
        self.release()
