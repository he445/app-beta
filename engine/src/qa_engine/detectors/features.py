"""Características compartilhadas: máscara de tinta e cobertura (ver blank_page.md)."""

from __future__ import annotations

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
