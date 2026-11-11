"""Tipos comuns aos detectores de página.

Um detector de página tem duas fases, para permitir comparar cada página com a
mediana do próprio lote (``docs/especificacoes/index.md``):

1. ``measure``: calcula as medidas de uma página, isoladamente.
2. ``evaluate``: compara as medidas com a linha de base do lote e decide se
   gera uma sinalização (:class:`Flag`).
"""

from __future__ import annotations

import math
import statistics
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from qa_engine.domain.model import ColorMode, Correction, Region, Severity
from qa_engine.ports import OrientationPrediction

ANALYSIS_DPI = 150.0
"""Resolução nominal do raster de análise."""

Params = Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class PageRaster:
    """Página pronta para análise.

    Attributes:
        gray: imagem em cinza 8 bits, reduzida a ``ANALYSIS_DPI``.
        scale: pixels do raster de análise por pixel do original.
        dpi: resolução gravada no arquivo original, se houver.
        color_mode: modo de cor do arquivo original.
        mean_saturation: saturação média (0 a 1) quando o original é colorido.
        orientation: orientação prevista pela porta ``OrientationClassifier``, se calculada.
    """

    gray: NDArray[np.uint8]
    scale: float
    dpi: float | None
    color_mode: ColorMode | None = None
    mean_saturation: float | None = None
    orientation: OrientationPrediction | None = None


@dataclass(frozen=True, slots=True)
class PageFeatures:
    """Características compartilhadas, calculadas uma vez por página."""

    ink: NDArray[np.bool_]
    """Máscara de tinta da página inteira, já sem pontilhado."""
    core: tuple[int, int, int, int]
    """Área útil (y0, y1, x0, x1), sem as margens."""
    ink_coverage: float
    """Fração da área útil coberta por tinta."""
    paper_level: float
    """Brilho do papel (percentil 90)."""


@dataclass(frozen=True, slots=True)
class Observation:
    """Medidas de uma página para um detector."""

    values: Mapping[str, float]
    eligible: bool = True
    """Se a página entra na linha de base do lote e é avaliada."""
    region: Region | None = None
    """Região no raster de análise."""
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Stats:
    """Estatística robusta de uma medida no lote."""

    median: float
    sigma: float
    """Desvio robusto: 1,4826 × MAD."""
    n: int


Baseline = Mapping[str, Stats]


@dataclass(frozen=True, slots=True)
class Flag:
    """Resultado de ``evaluate``: o que vira uma sinalização."""

    severity: Severity
    measure: float
    threshold: float
    confidence: float
    correction: Correction
    message: str
    region: Region | None = None
    """Região no raster de análise; a aplicação converte para o original."""


class PageDetector(Protocol):
    """Contrato de um detector de página."""

    id: str

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Calcula as medidas de uma página."""
        ...

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Compara as medidas com a linha de base e decide."""
        ...


def robust_stats(values: Iterable[float]) -> Stats:
    """Mediana e desvio robusto (1,4826 × MAD), ignorando valores não finitos."""
    data = [v for v in values if math.isfinite(v)]
    if not data:
        return Stats(median=math.nan, sigma=math.nan, n=0)
    median = statistics.median(data)
    mad = statistics.median(abs(v - median) for v in data)
    return Stats(median=median, sigma=1.4826 * mad, n=len(data))


def baseline_of(observations: Iterable[Observation]) -> dict[str, Stats]:
    """Linha de base do lote: estatística robusta de cada medida, só das páginas elegíveis."""
    columns: dict[str, list[float]] = {}
    for obs in observations:
        if not obs.eligible:
            continue
        for key, value in obs.values.items():
            columns.setdefault(key, []).append(value)
    return {key: robust_stats(vals) for key, vals in sorted(columns.items())}


def clamp01(value: float) -> float:
    """Limita ao intervalo [0, 1]."""
    return min(1.0, max(0.0, value))
