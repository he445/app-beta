"""Características compartilhadas: máscara de tinta e cobertura (ver blank_page.md)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import PageFeatures

MARGIN_FRACTION = 0.04
"""Margem ignorada em cada lado ao medir cobertura (bordas pretas, sombra do scanner)."""
MIN_SPECK_AREA = 6
"""Componentes com menos pixels que isso, a 150 dpi, são pontilhado."""
MIN_INK_DELTA = 40
"""Diferença mínima entre papel e tinta, em níveis de cinza."""


def ink_mask(gray: NDArray[np.uint8]) -> tuple[NDArray[np.bool_], float]:
    """Binariza a página: Otsu, limitado a ``papel - MIN_INK_DELTA``, sem pontilhado.

    Returns:
        A máscara de tinta e o brilho do papel (percentil 90).
    """
    paper = float(np.percentile(gray, 90))
    otsu, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    threshold = min(float(otsu), paper - MIN_INK_DELTA)
    raw = (gray <= threshold).astype(np.uint8)
    count, labels, stats, _ = cv2.connectedComponentsWithStats(raw, connectivity=8)
    keep = np.zeros(count, dtype=bool)
    keep[1:] = stats[1:, cv2.CC_STAT_AREA] >= MIN_SPECK_AREA
    return keep[labels], paper


def compute_features(gray: NDArray[np.uint8]) -> PageFeatures:
    """Calcula máscara de tinta, área útil e cobertura de tinta."""
    ink, paper = ink_mask(gray)
    h, w = gray.shape
    m = round(MARGIN_FRACTION * min(h, w))
    core = (m, max(m + 1, h - m), m, max(m + 1, w - m))
    y0, y1, x0, x1 = core
    area = ink[y0:y1, x0:x1]
    coverage = float(area.mean()) if area.size else 0.0
    return PageFeatures(ink=ink, core=core, ink_coverage=coverage, paper_level=paper)


class BoxKind(StrEnum):
    """O que uma caixa achada pelo detector de texto contém de verdade."""

    WRITING = "writing"
    """Tinta: conta como escrito (a folha não é branca) e segue para a leitura."""
    FAINT = "faint"
    """Traço fraco, sem tinta (possível número a lápis claro): branca só para revisão."""
    BACKGROUND = "background"
    """Fundo: transparência do verso, gradiente do papel. Ignorada."""


@dataclass(frozen=True, slots=True)
class InkCheck:
    """Confirmação de tinta dentro de uma caixa (``docs/especificacoes/detectors/blank_page.md``).

    O detector de texto normaliza o contraste e acha texto até na transparência do verso;
    quem decide se há tinta é o brilho dos pixels contra o papel da página.
    """

    paper: float
    """Brilho do papel da página (percentil 90, o mesmo da máscara de tinta)."""
    min_ink: float = 0.01
    """Fração mínima de pixels de tinta na caixa (``writing_min_ink``)."""
    min_pixels: int = 30
    """Pixels de tinta mínimos na caixa, a 150 dpi (``writing_min_pixels``)."""
    faint_delta: float = 26.0
    """Contraste (papel menos o percentil 5 da caixa) a partir do qual uma caixa sem tinta é
    traço fraco, não fundo (``faint_min_delta``)."""

    def classify(self, patch: NDArray[np.uint8]) -> BoxKind:
        """Classifica o conteúdo de uma caixa."""
        if patch.size == 0:
            return BoxKind.BACKGROUND
        dark = int(np.count_nonzero(patch <= self.paper - MIN_INK_DELTA))
        if dark >= self.min_pixels and dark / patch.size >= self.min_ink:
            return BoxKind.WRITING
        contrast = self.paper - float(np.percentile(patch, 5))
        return BoxKind.FAINT if contrast >= self.faint_delta else BoxKind.BACKGROUND
