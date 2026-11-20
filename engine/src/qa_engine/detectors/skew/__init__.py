"""Inclinação pelo perfil de projeção das linhas (``docs/especificacoes/detectors/skew.md``)."""

from __future__ import annotations

import math

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import (
    BASELINE_EXCLUDED,
    Baseline,
    Flag,
    Observation,
    PageFeatures,
    PageRaster,
    Params,
    clamp01,
)
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity


def _score(img: NDArray[np.uint8], angle: float) -> float:
    """Nitidez do perfil horizontal depois de girar ``angle`` graus (anti-horário).

    A máscara vai como ``uint8`` (0 ou 255) e a projeção sai de ``cv2.reduce`` em inteiro:
    o mesmo perfil da versão em ``float32``, a menos do arredondamento da interpolação.
    """
    h, w = img.shape
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    rotated = cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=0)
    rows = cv2.reduce(rotated, 1, cv2.REDUCE_SUM, dtype=cv2.CV_32S).ravel().astype(np.int64)
    return float(np.sum(np.diff(rows).astype(np.float64) ** 2))


def _search(
    img: NDArray[np.uint8],
    center: float,
    half: float,
    step: float,
    scores: dict[float, float],
    nudge: bool,
) -> float:
    """Melhor ângulo de ``center − half`` a ``center + half``; ``scores`` guarda o já medido.

    Com ``nudge``, o 0° é medido girando o mínimo que desloca a linha em um pixel de ponta
    a ponta (ver :data:`PASSES`).
    """
    count = round(2 * half / step)
    angles = [round(center - half + i * step, 6) for i in range(count + 1)]
    tiny = math.degrees(math.atan(1.0 / img.shape[1]))
    for a in angles:
        if a not in scores:
            scores[a] = _score(img, tiny if nudge and a == 0.0 else a)
    return max(angles, key=lambda a: scores[a])


PASSES = ((0.25, None, 1.0, True), (0.5, 1.0, 0.25, True), (1.0, 0.3, 0.05, False))
"""Busca em três passadas: (escala, meia-largura, passo, 0° desviado).

A primeira cobre ``max_angle``. Girar 0° não interpola e todo outro ângulo interpola: na
resolução reduzida isso dá a 0° um perfil mais nítido que o do ângulo certo, e a busca
grossa voltava para 0°. Nas passadas grossas o 0° é medido com um giro mínimo (um pixel
de deslocamento de ponta a ponta, menos que o passo), que interpola como os outros. A
passada final, na resolução cheia, mede 0° de verdade: pontua igual à versão anterior. Ela
parte do pico da passada do meio refinado por uma parábola, porque na metade da resolução
o pico é largo e puxado para 0°."""


def _vertex(scores: dict[float, float], best: float, step: float) -> float:
    """Pico da parábola pelos três pontos em volta de ``best``, no passo de 0,05°."""
    left, right = scores.get(round(best - step, 6)), scores.get(round(best + step, 6))
    if left is None or right is None:
        return best
    curve = left - 2.0 * scores[best] + right
    if curve >= 0:
        return best
    offset = 0.5 * step * (left - right) / curve
    return round(round((best + max(-step, min(step, offset))) / 0.05) * 0.05, 6)


def estimate_skew(ink: NDArray[np.bool_], max_angle: float) -> tuple[float, float]:
    """Estima a inclinação do conteúdo.

    Três passadas, da resolução mais baixa para a cheia: ±``max_angle`` de 1° em 1° a um
    quarto da resolução, ±1° de 0,25° em 0,25° na metade e ±0,3° de 0,05° em 0,05° na
    cheia, em volta do pico refinado da passada do meio.

    Returns:
        ``(ângulo, confiança)``. Ângulo em graus, positivo no sentido horário
        (convenção do contrato). Confiança heurística de 0 a 1.
    """
    full = ink.astype(np.uint8) * np.uint8(255)
    best = 0.0
    scores: dict[float, float] = {}
    for scale, half, step, nudge in PASSES:
        if scale < 1.0:
            img = cv2.resize(full, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
        else:
            img = full
            best = _vertex(scores, best, PASSES[1][2])
        scores = {}
        best = _search(img, best, max_angle if half is None else half, step, scores, nudge)
    s_best = scores[best]
    s_zero = scores[0.0] if 0.0 in scores else _score(full, 0.0)
    if s_zero >= s_best:
        return 0.0, 0.0  # nenhum ângulo achado pontua melhor que a página como está
    confidence = clamp01(2.0 * (s_best - s_zero) / s_best)
    # Girar +a (anti-horário no OpenCV) endireita conteúdo inclinado +a no sentido horário.
    return best, confidence


def straightened(gray: NDArray[np.uint8], angle: float) -> NDArray[np.uint8]:
    """Cópia em memória endireitada (``angle`` positivo = inclinada no sentido horário)."""
    h, w = gray.shape
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    paper = int(np.percentile(gray, 90))
    out = cv2.warpAffine(gray, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=paper)
    return np.ascontiguousarray(out, dtype=np.uint8)


ID = "skew"


class Skew:
    """Detector de inclinação."""

    id = ID

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Ângulo dominante das linhas de texto na área útil.

        Abaixo de ``min_ink_coverage`` e a partir de ``review_min_ink_coverage``, a página tem
        pouca tinta: é medida, mas só vai para revisão.
        """
        coverage = features.ink_coverage
        if coverage < float(params.get("review_min_ink_coverage", params["min_ink_coverage"])):
            return Observation({"angle": math.nan}, eligible=False)
        sparse = coverage < float(params["min_ink_coverage"])
        y0, y1, x0, x1 = features.core
        angle, confidence = estimate_skew(features.ink[y0:y1, x0:x1], float(params["max_angle"]))
        extra: dict[str, object] = {"confidence": confidence}
        if sparse:
            extra.update({"low_ink": True, BASELINE_EXCLUDED: True})
        return Observation({"angle": angle}, extra=extra)

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Sinaliza acima de ``flag_threshold``; acima de ``reject_threshold`` sobe para alto.

        A confiança decide o que acontece (ADR-0028): abaixo de ``min_flag_confidence`` o
        ângulo achado pontua igual a 0° e nada é sinalizado; até ``min_auto_confidence`` a
        página vai para revisão, sem correção automática.
        """
        if not obs.eligible:
            return None
        angle = obs.values["angle"]
        flag_at = float(params["flag_threshold"])
        if abs(angle) <= flag_at:
            return None
        confidence = float(obs.extra.get("confidence", 0.5))
        if confidence < float(params["min_flag_confidence"]):
            return None  # sem evidência: o ângulo achado pontua igual a 0°
        sparse = bool(obs.extra.get("low_ink"))
        if sparse and abs(angle) <= float(params["low_ink_min_angle"]):
            return None  # poucas linhas: a projeção é ruidosa em ângulo pequeno
        automatic = confidence >= float(params["min_auto_confidence"]) and not sparse
        reject = abs(angle) > float(params["reject_threshold"])
        direction = "horário" if angle > 0 else "anti-horário"
        correction_params: dict[str, object] = {"skew_deg": round(angle, 2)}
        description = f"Endireitar a página girando {abs(angle):.2f}° no sentido oposto."
        if sparse:
            correction_params.update({"review": True, "low_ink": True})
            description += " Página com pouca tinta: confira antes de aplicar (C)."
            confidence /= 2
        elif not automatic:
            correction_params["review"] = True
            description += " Evidência fraca: confira antes de aplicar (C)."
        return Flag(
            severity=Severity.HIGH if reject else Severity.MEDIUM,
            measure=abs(angle),
            threshold=flag_at,
            confidence=confidence,
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.DESKEW,
                description,
                correction_params,
            ),
            message=f"Inclinação de {abs(angle):.2f}° no sentido {direction}"
            + (" (acima do limite de reprovação)." if reject else "."),
        )


DETECTOR = Skew()
