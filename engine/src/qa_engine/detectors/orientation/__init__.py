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
    """Página branca não é classificada (não há texto para orientar)."""
    return bool(params["skip_blank"]) and features.ink_coverage < float(
        params["blank_ink_coverage"]
    )


def low_ink(features: PageFeatures, params: Params) -> bool:
    """Página com pouca tinta: classificada, mas só sinaliza com confiança alta e para revisão."""
    return bool(params["skip_blank"]) and features.ink_coverage < float(params["min_ink_coverage"])


def suggest_at(features: PageFeatures, params: Params) -> float:
    """Probabilidade mínima para a regra propor a rotação nesta página."""
    key = "auto_threshold" if low_ink(features, params) else "review_threshold"
    return float(params[key])


class Orientation:
    """Detector de orientação."""

    id = ID

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Ângulo previsto e probabilidade (sem previsão: página não elegível)."""
        prediction = page.orientation
        if prediction is None or skips(features, params):
            return Observation({"angle": math.nan, "probability": math.nan}, eligible=False)
        return Observation(
            {"angle": float(prediction.angle), "probability": float(prediction.probability)},
            extra={"low_ink": low_ink(features, params)},
        )

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Automática acima de ``auto_threshold``; para revisão acima de ``review_threshold``.

        Na página com pouca tinta, só sinaliza a partir de ``auto_threshold`` e sempre para
        revisão: pouco escrito engana o modelo, mas passar de lado calada é pior.
        """
        if not obs.eligible:
            return None
        angle = int(obs.values["angle"])
        probability = obs.values["probability"]
        auto_at = float(params["auto_threshold"])
        sparse = bool(obs.extra.get("low_ink"))
        review_at = auto_at if sparse else float(params["review_threshold"])
        if angle == 0 or probability < review_at:
            return None
        automatic = probability >= auto_at and not sparse
        turn = undo_angle(angle)
        correction_params: dict[str, object] = {"angle_deg": turn, "detected_deg": angle}
        if not automatic:
            correction_params["review"] = True
        if sparse:
            correction_params["low_ink"] = True
        if automatic:
            note = ""
        elif sparse:
            note = " Página com pouca tinta: confira antes de aplicar (C)."
        else:
            note = " Confiança média: confira antes de aplicar (C)."
        return Flag(
            severity=Severity.MEDIUM,
            measure=round(probability, 4),
            threshold=auto_at if automatic or sparse else review_at,
            confidence=round(probability, 4),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.ROTATE,
                f"Girar {turn}° no sentido horário na cópia." + note,
                correction_params,
            ),
            message=f"Página {LABEL[angle]} (confiança {probability:.0%}).",
        )


DETECTOR = Orientation()
