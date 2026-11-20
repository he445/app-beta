"""Inclinação pelo perfil de projeção das linhas (``docs/especificacoes/detectors/skew.md``)."""

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
        """Ângulo dominante das linhas de texto na área útil."""
        if features.ink_coverage < float(params["min_ink_coverage"]):
            return Observation({"angle": math.nan}, eligible=False)
        y0, y1, x0, x1 = features.core
        angle, confidence = estimate_skew(features.ink[y0:y1, x0:x1], float(params["max_angle"]))
        return Observation({"angle": angle}, extra={"confidence": confidence})

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
        automatic = confidence >= float(params["min_auto_confidence"])
        reject = abs(angle) > float(params["reject_threshold"])
        direction = "horário" if angle > 0 else "anti-horário"
        correction_params: dict[str, object] = {"skew_deg": round(angle, 2)}
        description = f"Endireitar a página girando {abs(angle):.2f}° no sentido oposto."
        if not automatic:
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
