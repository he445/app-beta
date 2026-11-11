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
from qa_engine.domain.settings import ResolvedSettings

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


class ReviewStore(Protocol):
    """Persistência das decisões, do painel e das operações de correção em lote."""

    def get_report(self, batch_id: str) -> dict[str, Any] | None:
        """Relatório com as sinalizações e decisões vigentes."""
        ...

    def record_decisions(
        self,
        batch_id: str,
        findings: Sequence[Mapping[str, Any]],
        summary: Mapping[str, Any] | None,
    ) -> None:
        """Grava as sinalizações decididas e o histórico, numa transação."""
        ...

    def clear_decisions(
        self,
        batch_id: str,
        findings: Sequence[Mapping[str, Any]],
        reviewer: str,
        at: str,
        operation_id: str | None,
        summary: Mapping[str, Any] | None,
    ) -> None:
        """Grava as sinalizações sem decisão e registra ``undo`` no histórico."""
        ...

    def set_summary(self, batch_id: str, summary: Mapping[str, Any]) -> None:
        """Atualiza o painel do lote."""
        ...

    def create_operation(self, operation: Mapping[str, Any]) -> None:
        """Registra uma operação de correção em lote."""
        ...

    def update_operation(self, operation_id: str, **fields: Any) -> None:
        """Atualiza campos da operação (progresso, estado, resultado)."""
        ...

    def get_operation(self, operation_id: str) -> dict[str, Any] | None:
        """Operação no formato de ``bulk-correction.schema.json`` (sem ``summary``)."""
        ...

    def list_operations(self, batch_id: str) -> list[dict[str, Any]]:
        """Operações do lote, da mais recente à mais antiga."""
        ...

    def decision_log(self, batch_id: str) -> list[dict[str, Any]]:
        """Histórico de decisões do lote (inclusive ``undo``), na ordem em que foram gravadas."""
        ...


class PageVersionStore(Protocol):
    """Cópias corrigidas das páginas e o log só de inserção que as descreve."""

    def events(self) -> list[dict[str, Any]]:
        """Eventos do log, na ordem em que foram gravados."""
        ...

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        """Grava um evento (recebe ``seq``) e o devolve."""
        ...

    def save(self, page_id: str, image: NDArray[np.uint8], dpi: float | None) -> tuple[str, str]:
        """Grava uma versão corrigida; devolve ``(nome, sha256)``."""
        ...

    def load(self, name: str) -> NDArray[np.uint8] | None:
        """Lê uma versão gravada, ou ``None`` se não existir mais."""
        ...


class CorrectedBatchWriter(Protocol):
    """Escreve o lote corrigido: páginas em formato sem perda e arquivos de texto."""

    def add_page(
        self,
        path: str,
        image: NDArray[np.uint8],
        dpi: float | None,
        bilevel: bool,
        tags: Mapping[str, str],
    ) -> str:
        """Grava uma página; devolve o SHA-256 do arquivo escrito."""
        ...

    def add_text(self, path: str, text: str) -> None:
        """Grava um arquivo de texto (manifesto)."""
        ...

    def close(self) -> tuple[Path, str, int]:
        """Finaliza; devolve ``(caminho, sha256, tamanho em bytes)``."""
        ...

    def abort(self) -> None:
        """Descarta o que foi escrito."""
        ...


class SettingsSource(Protocol):
    """Configuração deste computador, vinda de uma ou mais camadas."""

    def load(self) -> ResolvedSettings:
        """Configuração efetiva, com a origem de cada valor.

        Levanta ``SettingsError`` se alguma camada for inválida.
        """
        ...

    def save_user(self, changes: Mapping[str, Any], reset: Sequence[str] = ()) -> ResolvedSettings:
        """Grava mudanças na camada do usuário e devolve a configuração resultante."""
        ...


@dataclass(frozen=True, slots=True)
class FileStamp:
    """Tamanho e data de modificação de um arquivo, para saber se ele mudou."""

    size: int
    mtime_ns: int


class BatchFolder(Protocol):
    """Pasta de lote lida no lugar, local ou de rede (nunca alterada)."""

    def resolve(self, path: str) -> Path:
        """Caminho absoluto, no formato que o sistema abre sem limite de tamanho.

        Levanta ``FileNotFoundError`` se não existe e ``NotADirectoryError`` se não é pasta.
        """
        ...

    def listing(self, root: Path) -> dict[str, FileStamp]:
        """Arquivos do lote (caminho relativo com ``/``), sem ocultos; ilegíveis ficam de fora."""
        ...

    def sha256(self, path: Path) -> str | None:
        """SHA-256 do arquivo, ou ``None`` se ele não pôde ser lido (bloqueado, sem permissão)."""
        ...


@dataclass(frozen=True, slots=True)
class OrientationPrediction:
    """Orientação do conteúdo de uma página.

    ``angle`` é o giro horário que a página sofreu na digitalização (0, 90, 180 ou 270);
    para endireitar, gira-se ``(360 - angle) % 360`` no sentido horário.
    """

    angle: int
    probability: float
    probabilities: Mapping[int, float] = field(default_factory=dict)


class OrientationClassifier(Protocol):
    """Classifica a orientação de uma página (0°, 90°, 180° ou 270°)."""

    def classify(self, gray: NDArray[np.uint8]) -> OrientationPrediction:
        """Orientação mais provável e a probabilidade de cada ângulo."""
        ...
