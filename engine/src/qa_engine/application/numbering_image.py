"""Leitor de numeração por imagem: região → escritos → riscado → leituras → marcas.

Roda por página, dentro dos processos de análise, sobre a vista já orientada
(``docs/especificacoes/numeracao-por-imagem.md``). Entrega as marcas no formato que o
resolvedor de sequência já recebe (``Mark``), sem mudar nada nele: o resolvedor nunca
aceita uma leitura isolada, então um riscado que escapar ou uma leitura duvidosa é
decidida pela sequência do documento ou vai para o revisor.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass, field

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from qa_engine.detectors.strike import strike_score
from qa_engine.domain.sequencing import DIGIT_CONFUSIONS, Mark, Reading, parse_folio
from qa_engine.ports import TextBox, TextRecognizer, TextRegionDetector

Region = tuple[float, float, float, float]
DEFAULT_REGIONS: tuple[Region, ...] = ((0.60, 0.00, 1.00, 0.18),)
CORNERS: tuple[Region, ...] = (
    (0.60, 0.00, 1.00, 0.18),
    (0.00, 0.00, 0.40, 0.18),
    (0.60, 0.82, 1.00, 1.00),
    (0.00, 0.82, 0.40, 1.00),
)
"""Os quatro cantos: em página quase vazia a orientação não é confiável."""
SPLIT_GAP = 0.35
"""Vão vertical sem tinta, em alturas do escrito, que separa dois números numa caixa."""
MIN_READING = 0.3
"""Confiança mínima de uma leitura com formato de folha para virar marca."""
LONE_STRUCK = 0.99
"""Nota de riscado exigida quando a página tem um número só."""
EDGE_MARGIN = 0.01
"""Faixa junto à borda da página (fração do lado menor) ignorada na busca nos cantos."""
Confusion = tuple[str, str, float]
"""Dígito lido, alternativa e peso (confiança da alternativa relativa à leitura)."""
DEFAULT_CONFUSIONS: tuple[Confusion, ...] = tuple((a, b, 0.5) for a, b in DIGIT_CONFUSIONS)
"""Trocas que a letra de mão provoca: o 1 com serifa e o 7; o 2 com laço e o 9; o 9 com
rabo longo e o 0; 3 e 5; 7 e 9; 6 e 0 (relatório de testes de 18/11/2026)."""
MAX_READINGS = 5
"""Leituras por marca: as do reconhecedor primeiro, depois as alternativas."""
MAX_ASPECT = 5.0
"""Caixa mais larga que isso (em alturas) é linha de texto impresso, não número de folha."""


@dataclass(frozen=True, slots=True)
class PageNumberingRead:
    """O que o leitor achou numa página."""

    marks: tuple[Mark, ...] = ()
    written: bool = False
    """Algum escrito na região (mesmo ilegível ou riscado): a página não é branca."""
    crop_png: bytes | None = None
    """Recorte da região onde a numeração foi procurada, para a tela de Sequência."""
    boxes: tuple[TextBox, ...] = field(default_factory=tuple)


def crop_fraction(gray: NDArray[np.uint8], region: Region) -> tuple[NDArray[np.uint8], int, int]:
    """Recorta a região em frações da página; devolve o recorte e o canto superior esquerdo."""
    h, w = gray.shape[:2]
    x0, y0 = int(region[0] * w), int(region[1] * h)
    x1, y1 = max(x0 + 1, int(region[2] * w)), max(y0 + 1, int(region[3] * h))
    return np.ascontiguousarray(gray[y0:y1, x0:x1]), x0, y0


def split_box(gray: NDArray[np.uint8], box: TextBox) -> list[TextBox]:
    """Divide uma caixa em dois escritos quando há um vão vertical sem tinta largo o bastante.

    O detector às vezes junta dois números escritos lado a lado ("3" e "8" viram "38").
    """
    patch = gray[box.y : box.y + box.h, box.x : box.x + box.w]
    if patch.size == 0:
        return [box]
    _, ink = cv2.threshold(patch, 0, 1, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    columns = ink.sum(axis=0) > max(1, box.h // 25)
    gap_needed = max(2, int(SPLIT_GAP * box.h))
    parts: list[tuple[int, int]] = []
    start: int | None = None
    blank = 0
    for i, has_ink in enumerate(columns):
        if has_ink:
            if start is None:
                start = i
            elif blank >= gap_needed:
                parts.append((start, i - blank))
                start = i
            blank = 0
        elif start is not None:
            blank += 1
    if start is not None:
        parts.append((start, len(columns) - blank))
    if len(parts) <= 1:
        return [box]
    return [TextBox(box.x + a, box.y, max(1, b - a), box.h, box.score) for a, b in parts]


class ImageNumberingReader:
    """Lê a numeração de folha escrita à mão numa página já orientada."""

    def __init__(
        self,
        detector: TextRegionDetector,
        recognizer: TextRecognizer,
        struck_threshold: float = 0.6,
        min_height_mm: float = 3.0,
        fallback: TextRegionDetector | None = None,
        confusions: Sequence[Confusion] = DEFAULT_CONFUSIONS,
    ) -> None:
        self.detector = detector
        self.confusions = tuple(confusions)
        self.fallback = fallback
        self.recognizer = recognizer
        self.struck_threshold = struck_threshold
        self.min_height_mm = min_height_mm

    def _min_height(self, dpi: float) -> int:
        return max(8, round(self.min_height_mm / 25.4 * dpi))

    def read(
        self, gray: NDArray[np.uint8], dpi: float, regions: Sequence[Region] = DEFAULT_REGIONS
    ) -> PageNumberingRead:
        """Procura nas regiões em ordem e para na primeira que tiver número de folha.

        Args:
            gray: página em cinza, já de pé.
            dpi: resolução de ``gray`` (para a altura mínima de um escrito).
            regions: regiões em frações da página ``(x0, y0, x1, y1)``.
        """
        written = False
        first_crop: bytes | None = None
        for region in regions:
            crop, _, _ = crop_fraction(gray, region)
            if first_crop is None:
                first_crop = _png(crop)
            boxes = [
                part
                for box in self._detect(crop)
                if box.h >= self._min_height(dpi) and box.w <= MAX_ASPECT * box.h
                for part in split_box(crop, box)
            ]
            if boxes:
                written = True
            marks: list[Mark] = []
            scores: list[float] = []
            for box in boxes:
                patch = crop[box.y : box.y + box.h, box.x : box.x + box.w]
                readings = candidate_readings(
                    [(r.text, r.confidence) for r in self.recognizer.read(patch)],
                    self.confusions,
                )
                if not readings:
                    continue  # palavra impressa ou rabisco: não é número de folha
                scores.append(strike_score(_padded(crop, box)))
                marks.append(Mark(readings))
            if marks:
                # Sozinho na página, um número riscado é raro (quem risca escreve o novo ao
                # lado): exige nota máxima para não confundir o traço do meio de um 4 ou 7.
                limit = self.struck_threshold if len(marks) > 1 else LONE_STRUCK
                marks = [Mark(m.readings, sc >= limit) for m, sc in zip(marks, scores, strict=True)]
                return PageNumberingRead(tuple(marks), True, _png(crop), tuple(boxes))
        return PageNumberingRead((), written, first_crop)

    def _detect(self, crop: NDArray[np.uint8]) -> list[TextBox]:
        """Caixas do modelo e, do plano B, as que não se sobrepõem a nenhuma (traço fino)."""
        boxes = list(self.detector.detect(crop))
        if self.fallback is not None:
            extra = [
                b for b in self.fallback.detect(crop) if not any(_overlaps(b, o) for o in boxes)
            ]
            boxes += extra
        return sorted(boxes, key=lambda b: (b.y, b.x))

    def has_writing(self, gray: NDArray[np.uint8], dpi: float) -> bool:
        """Algum escrito em qualquer um dos quatro cantos (página quase vazia).

        Caixa encostada na borda da página é sombra ou borda do digitalizador, não escrito.
        """
        h, w = gray.shape[:2]
        edge = max(2, round(EDGE_MARGIN * min(h, w)))
        for region in CORNERS:
            crop, x0, y0 = crop_fraction(gray, region)
            for b in self._detect(crop):
                if b.h < self._min_height(dpi) or b.w > MAX_ASPECT * b.h:
                    continue
                x, y = x0 + b.x, y0 + b.y
                if x <= edge or y <= edge or x + b.w >= w - edge or y + b.h >= h - edge:
                    continue
                return True
        return False


def candidate_readings(
    raw: Sequence[tuple[str, float]],
    confusions: Sequence[Confusion] = DEFAULT_CONFUSIONS,
    limit: int = MAX_READINGS,
) -> tuple[Reading, ...]:
    """Leituras de um escrito que viram marca (etapa 4 da especificação).

    Ficam as leituras com formato de folha; o escrito só vira marca se a melhor tiver
    confiança de pelo menos ``MIN_READING``. As outras leituras do reconhecedor ficam
    mesmo com confiança baixa (são a segunda opção dele), e as alternativas de
    :func:`with_confusions` completam até ``limit``.
    """
    readings = sorted(
        (Reading(text, conf) for text, conf in raw if parse_folio(text) is not None),
        key=lambda r: -r.confidence,
    )
    if not readings or readings[0].confidence < MIN_READING:
        return ()
    return with_confusions(readings, confusions, limit)


def with_confusions(
    readings: Sequence[Reading],
    confusions: Sequence[Confusion] = DEFAULT_CONFUSIONS,
    limit: int = MAX_READINGS,
) -> tuple[Reading, ...]:
    """Acrescenta alternativas com um dígito trocado, com confiança menor.

    O reconhecedor às vezes tem certeza do dígito errado ("72-A" no lugar de "12-A",
    "1990" no lugar de "1920") e a leitura certa nem aparece. Cada dígito da leitura mais
    confiável que está na tabela gera a alternativa trocada, com a confiança multiplicada
    pelo peso do par; um dígito por vez. As leituras do reconhecedor têm prioridade; as
    alternativas completam até ``limit``, as de maior confiança primeiro e, no empate, as
    mais à direita (o dígito que muda de uma folha para a seguinte). O resolvedor decide
    pela sequência do documento e nunca aceita uma alternativa sozinha: escolhida, a
    página vai para o revisor como inferida.
    """
    if not readings:
        return ()
    own = sorted(readings, key=lambda r: -r.confidence)[:limit]
    seen = {r.text for r in own}
    source = own[0]
    options: list[tuple[float, int, int, str]] = []
    for i, ch in enumerate(source.text):
        for order, (read, alternative, weight) in enumerate(confusions):
            if ch != read:
                continue
            text = source.text[:i] + alternative + source.text[i + 1 :]
            if text not in seen and parse_folio(text) is not None:
                seen.add(text)
                options.append((source.confidence * weight, i, order, text))
    options.sort(key=lambda o: (-o[0], -o[1], o[2]))
    extra = [Reading(text, conf) for conf, _, _, text in options[: limit - len(own)]]
    return tuple(sorted([*own, *extra], key=lambda r: -r.confidence))


def _overlaps(a: TextBox, b: TextBox) -> bool:
    return a.x < b.x + b.w and b.x < a.x + a.w and a.y < b.y + b.h and b.y < a.y + a.h


def _padded(gray: NDArray[np.uint8], box: TextBox, margin: float = 0.3) -> NDArray[np.uint8]:
    """O escrito com uma margem: o traço do risco costuma passar da caixa do detector."""
    dx, dy = round(box.w * margin), round(box.h * margin)
    h, w = gray.shape[:2]
    y0, y1 = max(0, box.y - dy), min(h, box.y + box.h + dy)
    x0, x1 = max(0, box.x - dx), min(w, box.x + box.w + dx)
    return np.ascontiguousarray(gray[y0:y1, x0:x1])


def _png(gray: NDArray[np.uint8]) -> bytes:
    buffer = io.BytesIO()
    Image.fromarray(gray).save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()
