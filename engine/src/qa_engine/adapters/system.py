"""Relógio e executores."""

from __future__ import annotations

import concurrent.futures
import ctypes
import multiprocessing
import os
import sys
from collections.abc import Callable, Iterable, Iterator
from datetime import UTC, datetime
from typing import TypeVar

T = TypeVar("T")
R = TypeVar("R")


class SystemClock:
    """Relógio do sistema, em UTC."""

    def now(self) -> datetime:
        """Agora, em UTC."""
        return datetime.now(tz=UTC)


class FixedClock:
    """Relógio fixo para testes e execuções reprodutíveis."""

    def __init__(self, instant: datetime) -> None:
        self._instant = instant

    def now(self) -> datetime:
        """O instante fixado."""
        return self._instant


class SerialExecutor:
    """Executa em série, no próprio processo."""

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> Iterator[R]:
        """Aplica ``fn`` em ordem."""
        return map(fn, items)


class ProcessPoolExecutor:
    """Pool de processos que usa todos os núcleos (porta ``Executor``)."""

    def __init__(self, workers: int | None = None) -> None:
        self._workers = workers

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> Iterator[R]:
        """Aplica ``fn`` em paralelo, preservando a ordem."""
        # forkserver: seguro quando chamado de uma thread (API); spawn fora do Linux.
        method = "forkserver" if sys.platform.startswith("linux") else "spawn"
        context = multiprocessing.get_context(method)
        with concurrent.futures.ProcessPoolExecutor(
            max_workers=self._workers, mp_context=context
        ) as pool:
            yield from pool.map(fn, items, chunksize=4)


def total_memory_mb() -> int | None:
    """Memória física do computador em MB, ou ``None`` se o sistema não informar."""
    if sys.platform == "win32":

        class _MemoryStatus(ctypes.Structure):
            _fields_ = (
                ("length", ctypes.c_ulong),
                ("load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong),
                ("avail_phys", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("avail_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended", ctypes.c_ulonglong),
            )

        status = _MemoryStatus()
        status.length = ctypes.sizeof(_MemoryStatus)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.total_phys // (1024 * 1024))
    try:
        return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") // (1024 * 1024))
    except (ValueError, OSError, AttributeError):
        return None
