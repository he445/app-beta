"""Riscado: nota de 0 a 1 de um escrito estar riscado.

Especificação: ``docs/especificacoes/numeracao-por-imagem.md``.

Um número riscado tem um traço longo e quase reto atravessando a faixa do meio do
escrito (pelo menos 60% da largura), ou dois traços cruzados em X. Dígitos à mão
quase nunca têm traço horizontal tão longo na faixa do meio.
"""

from __future__ import annotations

import math

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import clamp01
from qa_engine.ports import as_u8

MIN_SPAN = 0.6
"""Fração da largura que o traço precisa atravessar para contar."""


def _ink(gray: NDArray[np.uint8]) -> NDArray[np.uint8]:
    # Relativo ao papel, não Otsu: o traço do risco costuma ser fino e mais claro que o
    # número, e a 150 dpi o Otsu o jogaria fora.
    paper = float(np.percentile(gray, 90))
    return as_u8((gray < paper - 40).astype(np.uint8) * 255)


def _segments(ink: NDArray[np.uint8], min_length: int) -> list[tuple[float, float, float, float]]:
    lines = cv2.HoughLinesP(
        ink,
        1,
        np.pi / 180,
        threshold=max(10, min_length // 2),
        minLineLength=min_length,
        maxLineGap=max(2, min_length // 12),
    )
    if lines is None:
        return []
    return [
        (float(a), float(b), float(c), float(d)) for a, b, c, d in np.asarray(lines).reshape(-1, 4)
    ]


def _passes_glyph(
    ink: NDArray[np.uint8], seg: tuple[float, float, float, float], w: int, ih: int
) -> bool:
    """O traço chega às bordas do resto do escrito e passa de pelo menos uma.

    O resto é a tinta fora da faixa do próprio traço. Separa o risco (que atravessa e
    sobra) do traço do meio de um 4 ou de um 7 cortado (que termina na diagonal).
    """
    x0, y0, x1, y1 = seg
    band = max(2, round(0.12 * ih))
    lo, hi = int(min(y0, y1)) - band, int(max(y0, y1)) + band
    rest = ink.copy()
    rest[max(0, lo) : hi + 1, :] = 0
    cols = np.nonzero(rest.any(axis=0))[0]
    if cols.size == 0:
        return True
    a, b = min(x0, x1), max(x0, x1)
    margin = 0.04 * w
    reaches = a <= cols[0] + 0.02 * w and b >= cols[-1] - 0.02 * w
    return bool(reaches and (a <= cols[0] - margin or b >= cols[-1] + margin))


def strike_score(gray: NDArray[np.uint8], width: int | None = None) -> float:
    """Nota de riscado do escrito recortado (0 = limpo, 1 = riscado com certeza).

    A largura de referência é a extensão horizontal da tinta no recorte (a caixa do
    detector costuma ser mais larga que o escrito). Traço horizontal (até 25° de
    inclinação) com o meio na faixa de 30% a 70% da altura da tinta e cobrindo pelo
    menos 85% da extensão da tinta: nota = (extensão/largura − 0,5) / 0,4, limitada a
    [0, 1]. Dois traços de inclinações opostas (entre 8° e 82°), cada um com pelo menos
    60% da diagonal da tinta e cruzando na parte central dela, dão 1. ``width`` fica por
    compatibilidade: quando há tinta, a largura medida é a dela.
    """
    h, full = gray.shape[:2]
    if h < 8 or full < 8:
        return 0.0
    ink = _ink(gray)
    cols = np.nonzero(ink.any(axis=0))[0]
    rows = np.nonzero(ink.any(axis=1))[0]
    if cols.size < 8 or rows.size < 8:
        return 0.0
    left, right = int(cols[0]), int(cols[-1])
    top, bottom = int(rows[0]), int(rows[-1])
    w = max(8, right - left + 1)
    ih = max(8, bottom - top + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, w // 6), 1))
    thin = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
    best = 0.0
    for x0, y0, x1, y1 in _segments(thin, max(8, int(w * MIN_SPAN))):
        angle = abs(math.degrees(math.atan2(y1 - y0, x1 - x0)))
        angle = min(angle, 180 - angle)
        middle = top + 0.3 * ih <= (y0 + y1) / 2 <= top + 0.7 * ih
        covers = min(x0, x1) <= left + 0.15 * w and max(x0, x1) >= right - 0.15 * w
        if angle <= 25 and middle and covers and _passes_glyph(ink, (x0, y0, x1, y1), w, ih):
            best = max(best, clamp01((abs(x1 - x0) / w - 0.5) / 0.4))
    diagonal = math.hypot(w, ih)

    def slope(seg: tuple[float, float, float, float]) -> float:
        x0, y0, x1, y1 = seg
        a = abs(math.degrees(math.atan2(y1 - y0, x1 - x0)))
        return min(a, 180 - a)

    def crosses_center(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
        """As duas retas se cruzam na parte central da tinta (não na ponta de um 4)."""
        x1, y1, x2, y2 = a
        x3, y3, x4, y4 = b
        den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
        if abs(den) < 1e-9:
            return False
        px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / den
        py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / den
        return left + 0.3 * w <= px <= right - 0.3 * w and top + 0.3 * ih <= py <= bottom - 0.3 * ih

    # X: dois traços longos de inclinações opostas, do tamanho da diagonal da tinta,
    # cruzando no centro (número largo deixa a diagonal rasa).
    slants = [s for s in _segments(ink, max(8, int(diagonal * MIN_SPAN))) if 8 < slope(s) < 82]
    rising = [s for s in slants if (s[3] - s[1]) * (s[2] - s[0]) < 0]
    falling = [s for s in slants if (s[3] - s[1]) * (s[2] - s[0]) > 0]
    if any(crosses_center(a, b) for a in rising for b in falling):
        best = 1.0
    return round(best, 4)
