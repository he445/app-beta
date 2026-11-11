"""Orientação da página (``docs/especificacoes/detectors/orientation.md``).

A classificação vem da porta ``OrientationClassifier``, chamada pela aplicação;
o detector só decide o que vira sinalização.
"""

from __future__ import annotations

import math

from qa_engine.detectors.base import (
    Baseline,
    Flag,
    Observation,
    PageFeatures,
    PageRaster,
    Params,
)
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity

ID = "orientation"
LABEL = {
    90: "de lado (girada para a direita)",
    180: "de cabeça para baixo",
    270: "de lado (girada para a esquerda)",
}


def undo_angle(angle: int) -> int:
    """Giro horário que desfaz a orientação detectada."""
    return (360 - angle) % 360


def skips(features: PageFeatures, params: Params) -> bool:
    """Página quase sem tinta não é classificada (não há texto para orientar)."""
    return bool(params["skip_blank"]) and features.ink_coverage < float(params["min_ink_coverage"])


class Orientation:
    """Detector de orientação."""

    id = ID

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Ângulo previsto e probabilidade (sem previsão: página não elegível)."""
        prediction = page.orientation
        if prediction is None or skips(features, params):
            return Observation({"angle": math.nan, "probability": math.nan}, eligible=False)
        return Observation(
            {"angle": float(prediction.angle), "probability": float(prediction.probability)}
        )

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Automática acima de ``auto_threshold``; para revisão acima de ``review_threshold``."""
        if not obs.eligible:
            return None
        angle = int(obs.values["angle"])
        probability = obs.values["probability"]
        review_at = float(params["review_threshold"])
        if angle == 0 or probability < review_at:
            return None
        automatic = probability >= float(params["auto_threshold"])
        turn = undo_angle(angle)
        correction_params: dict[str, object] = {"angle_deg": turn, "detected_deg": angle}
        if not automatic:
            correction_params["review"] = True
        return Flag(
            severity=Severity.MEDIUM,
            measure=round(probability, 4),
            threshold=float(params["auto_threshold"] if automatic else review_at),
            confidence=round(probability, 4),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.ROTATE,
                f"Girar {turn}° no sentido horário na cópia."
                + ("" if automatic else " Confiança média: confira antes de aplicar (C)."),
                correction_params,
            ),
            message=f"Página {LABEL[angle]} (confiança {probability:.0%}).",
        )


DETECTOR = Orientation()
