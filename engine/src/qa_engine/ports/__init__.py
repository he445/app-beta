"""Portas: interfaces que a aplicação usa e os adaptadores implementam (ADR-0003)."""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol, TypeVar

import numpy as np
from numpy.typing import NDArray

from qa_engine.domain.model import ColorMode
from qa_engine.domain.sequencing import Mark

T = TypeVar("T")
R = TypeVar("R")


def as_u8(array: Any) -> NDArray[np.uint8]:
    """Tipa como ``uint8`` o retorno das bibliotecas de imagem (sem copiar se já for)."""
    return np.asarray(array, dtype=np.uint8)


class LoadError(Exception):
    """Falha ao decodificar um arquivo ou uma página (vira ``corrupted_file``)."""


@dataclass(frozen=True, slots=True)
class LoadedPage:
    """Página decodificada, já reduzida para análise."""

    gray: NDArray[np.uint8]
    scale: float
    """Pixels de análise por pixel original."""
    width_px: int
    height_px: int
    dpi: float | None
    color_mode: ColorMode | None
    mean_saturation: float | None


class ImageSource(Protocol):
    """Lê páginas de arquivos TIFF, JPG, PNG e PDF."""

    def page_count(self, path: Path) -> int:
        """Número de páginas do arquivo. Levanta :class:`LoadError` se ilegível."""
        ...

    def load(self, path: Path, page_in_file: int, analysis_dpi: float) -> LoadedPage:
        """Decodifica uma página e a reduz a ``analysis_dpi``."""
        ...

    def load_original(self, path: Path, page_in_file: int) -> NDArray[np.uint8]:
        """Decodifica uma página em resolução original (cinza ou RGB)."""
        ...


@dataclass(frozen=True, slots=True)
class FileMetadata:
    """Metadados técnicos e de captura lidos de um arquivo."""

    format: str
    size_bytes: int
    sha256: str
    page_count: int
    tags: Mapping[str, Any] = field(default_factory=dict)
    """Tags normalizadas: ``datetime``, ``make``, ``model``, ``software``, ``artist``,
    ``serial``, ``compression``, ``bits``, ``dpi``, ``width_px``, ``height_px``."""
    modified_at: datetime | None = None


class MetadataReader(Protocol):
    """Lê metadados técnicos de um arquivo."""

    def read(self, path: Path) -> FileMetadata:
        """Metadados do arquivo. Não levanta exceção por tag ausente."""
        ...


class NumberingReader(Protocol):
    """Lê as marcas de numeração de folhas de cada página."""

    def read(self, batch_root: Path, page_keys: Sequence[str]) -> Mapping[str, Sequence[Mark]]:
        """Marcas por chave de página (``caminho/relativo#n``)."""
        ...


class Clock(Protocol):
    """Fonte de tempo, para testes determinísticos."""

    def now(self) -> datetime:
        """Data e hora atual em UTC."""
        ...


class Executor(Protocol):
    """Executa uma função sobre itens, possivelmente em paralelo, preservando a ordem."""

    def map(self, fn: Callable[[T], R], items: Iterable[T]) -> Iterator[R]:
        """Aplica ``fn`` a cada item e devolve os resultados na ordem de entrada."""
        ...
