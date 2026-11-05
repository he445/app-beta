"""Inclinação: perfil de projeção das linhas de texto (``spec/detectors/skew.md``)."""

from __future__ import annotations

import math

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.detectors.base import (
    Baseline,
    Flag,
    Observation,
    PageFeatures,
    PageRaster,
    Params,
    clamp01,
)
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity


def _score(img: NDArray[np.float32], angle: float) -> float:
    """Nitidez do perfil horizontal depois de girar ``angle`` graus (anti-horário)."""
    h, w = img.shape
    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
    rotated = cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_LINEAR, borderValue=0.0)
    rows = rotated.sum(axis=1, dtype=np.float64)
    return float(np.sum(np.diff(rows) ** 2))


def _search(img: NDArray[np.float32], center: float, half: float, step: float) -> float:
    count = round(2 * half / step)
    angles = [round(center - half + i * step, 6) for i in range(count + 1)]
    scores = [_score(img, a) for a in angles]
    return angles[int(np.argmax(scores))]


def estimate_skew(ink: NDArray[np.bool_], max_angle: float) -> tuple[float, float]:
    """Estima a inclinação do conteúdo.

    Returns:
        ``(ângulo, confiança)``. Ângulo em graus, positivo no sentido horário
        (convenção do contrato). Confiança heurística de 0 a 1.
    """
    full = ink.astype(np.float32)
    coarse = cv2.resize(full, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    best = _search(coarse, 0.0, max_angle, 0.5)
    best = _search(full, best, 0.6, 0.05)
    s_best, s_zero = _score(full, best), _score(full, 0.0)
    confidence = clamp01(2.0 * (s_best - s_zero) / s_best) if s_best > 0 else 0.0
    # Girar +a (anti-horário no OpenCV) endireita conteúdo inclinado +a no sentido horário.
    return best, confidence


class Skew:
    """Detector de inclinação."""

    id = "skew"

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Ângulo dominante das linhas de texto na área útil."""
        if features.ink_coverage < float(params["min_ink_coverage"]):
            return Observation({"angle": math.nan}, eligible=False)
        y0, y1, x0, x1 = features.core
        angle, confidence = estimate_skew(features.ink[y0:y1, x0:x1], float(params["max_angle"]))
        return Observation({"angle": angle}, extra={"confidence": confidence})

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Sinaliza acima de ``flag_threshold``; acima de ``reject_threshold`` sobe para alto."""
        if not obs.eligible:
            return None
        angle = obs.values["angle"]
        flag_at = float(params["flag_threshold"])
        if abs(angle) <= flag_at:
            return None
        reject = abs(angle) > float(params["reject_threshold"])
        direction = "horário" if angle > 0 else "anti-horário"
        return Flag(
            severity=Severity.HIGH if reject else Severity.MEDIUM,
            measure=abs(angle),
            threshold=flag_at,
            confidence=float(obs.extra.get("confidence", 0.5)),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.DESKEW,
                f"Endireitar a página girando {abs(angle):.2f}° no sentido oposto.",
                {"skew_deg": round(angle, 2)},
            ),
            message=f"Inclinação de {abs(angle):.2f}° no sentido {direction}"
            + (" (acima do limite de reprovação)." if reject else "."),
        )


DETECTOR = Skew()
