"""Página duplicada: dHash + correlação de miniaturas.

Especificação: ``docs/especificacoes/detectors/duplicate_page.md``.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import Params
from qa_engine.ports import as_u8

ID = "duplicate_page"
THUMB_WIDTH = 128
THUMB_SIGMA = 1.0
HASH_SIZE = 16


@dataclass(frozen=True, slots=True)
class Fingerprint:
    """Impressão digital de uma página para comparação."""

    page_id: str
    dhash: int
    thumb: NDArray[np.uint8]
    sharpness: float
    eligible: bool


@dataclass(frozen=True, slots=True)
class DuplicatePair:
    """Par de páginas quase idênticas; ``copy`` é a de pior qualidade."""

    copy: str
    original: str
    similarity: float
    hash_distance: int


def dhash(gray: NDArray[np.uint8], size: int = HASH_SIZE) -> int:
    """Hash de diferença de ``size`` × ``size`` bits."""
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA).astype(np.int16)
    bits = (small[:, 1:] > small[:, :-1]).flatten()
    value = 0
    for bit in bits:
        value = (value << 1) | int(bit)
    return value


def thumbnail(gray: NDArray[np.uint8]) -> NDArray[np.uint8]:
    """Miniatura de largura fixa, suavizada, usada na verificação por correlação.

    A suavização torna a comparação tolerante ao deslocamento de poucos pixels
    entre duas capturas da mesma folha.
    """
    h, w = gray.shape
    height = max(1, round(h * THUMB_WIDTH / w))
    small = cv2.resize(gray, (THUMB_WIDTH, height), interpolation=cv2.INTER_AREA)
    return as_u8(cv2.GaussianBlur(small, (0, 0), THUMB_SIGMA))


def _ncc(a: NDArray[np.uint8], b: NDArray[np.uint8]) -> float:
    if a.shape != b.shape:
        b = cv2.resize(b, (a.shape[1], a.shape[0]), interpolation=cv2.INTER_AREA)
    x = a.astype(np.float64) - a.mean()
    y = b.astype(np.float64) - b.mean()
    denom = float(np.sqrt((x * x).sum() * (y * y).sum()))
    return float((x * y).sum() / denom) if denom > 0 else 0.0


def find_duplicates(prints: Sequence[Fingerprint], params: Params) -> list[DuplicatePair]:
    """Compara todos os pares elegíveis do lote (O(n²) no hash, correlação só nos candidatos)."""
    max_bits = int(params["max_hash_distance"])
    min_sim = float(params["min_similarity"])
    pairs: list[DuplicatePair] = []
    flagged: set[str] = set()
    eligible = [p for p in prints if p.eligible]
    for i, first in enumerate(eligible):
        for second in eligible[i + 1 :]:
            distance = (first.dhash ^ second.dhash).bit_count()
            if distance > max_bits:
                continue
            similarity = _ncc(first.thumb, second.thumb)
            if similarity < min_sim:
                continue
            # A cópia é a menos nítida; em empate, a que vem depois.
            copy, original = (
                (first, second) if first.sharpness < second.sharpness else (second, first)
            )
            if copy.page_id in flagged:
                continue
            flagged.add(copy.page_id)
            pairs.append(DuplicatePair(copy.page_id, original.page_id, similarity, distance))
    return pairs
