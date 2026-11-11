"""Relógio e executores."""

from __future__ import annotations

import concurrent.futures
import multiprocessing
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
