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
from qa_engine.ports import OrientationPrediction

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


def upright_probability(prediction: OrientationPrediction) -> float:
    """Probabilidade de a página estar de pé (0°).

    Sem as probabilidades de cada ângulo, usa o maior valor possível: a própria
    probabilidade se o mais provável é 0°, senão ``1 − p``.
    """
    if 0 in prediction.probabilities:
        return float(prediction.probabilities[0])
    p = float(prediction.probability)
    return p if prediction.angle == 0 else 1.0 - p


def runner_up(prediction: OrientationPrediction) -> tuple[int, float] | None:
    """Rotação (ângulo diferente de 0°) mais provável e sua probabilidade."""
    rotated = {a: float(v) for a, v in prediction.probabilities.items() if a != 0}
    if not rotated:
        return (prediction.angle, float(prediction.probability)) if prediction.angle else None
    angle = max(rotated, key=lambda a: rotated[a])
    return angle, rotated[angle]


def suggest_at(features: PageFeatures, params: Params) -> float:
    """Probabilidade mínima para a regra propor a rotação nesta página.

    Também na página com pouca tinta é ``review_threshold``: ela vai sempre para revisão.
    """
    return float(params["review_threshold"])


class Orientation:
    """Detector de orientação."""

    id = ID

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Ângulo previsto e probabilidade (sem previsão: página não elegível)."""
        prediction = page.orientation
        if prediction is None or skips(features, params):
            return Observation({"angle": math.nan, "probability": math.nan}, eligible=False)
        return Observation(
            {
                "angle": float(prediction.angle),
                "probability": float(prediction.probability),
                "upright_probability": upright_probability(prediction),
            },
            extra={"low_ink": low_ink(features, params), "runner_up": runner_up(prediction)},
        )

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Automática acima de ``auto_threshold``; para revisão acima de ``review_threshold``.

        Na página com pouca tinta, sinaliza a partir de ``review_threshold`` e sempre para
        revisão: pouco escrito engana o modelo, mas passar de lado calada é pior.
        """
        if not obs.eligible:
            return None
        angle = int(obs.values["angle"])
        probability = obs.values["probability"]
        auto_at = float(params["auto_threshold"])
        sparse = bool(obs.extra.get("low_ink"))
        review_at = float(params["review_threshold"])
        if angle == 0 or probability < review_at:
            if sparse:
                return None  # carimbo e rubrica: sem sentido de leitura, o modelo espalha
            return self._uncertain(obs, params)
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
            threshold=auto_at if automatic else review_at,
            confidence=round(probability, 4),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.ROTATE,
                f"Girar {turn}° no sentido horário na cópia." + note,
                correction_params,
            ),
            message=f"Página {LABEL[angle]} (confiança {probability:.0%}).",
        )

    @staticmethod
    def _uncertain(obs: Observation, params: Params) -> Flag | None:
        """Nenhuma rotação convence e 0° também não: "não sei" vai para revisão."""
        upright = obs.values.get("upright_probability", math.nan)
        floor = float(params["upright_min_probability"])
        best = obs.extra.get("runner_up")
        if not math.isfinite(upright) or upright >= floor or best is None:
            return None
        angle, probability = int(best[0]), float(best[1])
        turn = undo_angle(angle)
        return Flag(
            severity=Severity.MEDIUM,
            measure=round(upright, 4),
            threshold=floor,
            confidence=round(1.0 - upright, 4),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.ROTATE,
                f"Rotação mais provável: girar {turn}° no sentido horário na cópia. "
                "Confira a página antes de aplicar (C) ou deixe de pé.",
                {"angle_deg": turn, "detected_deg": angle, "review": True, "uncertain": True},
            ),
            message=(
                f"Orientação incerta: o modelo não confirma a página de pé (0°: {upright:.0%}); "
                f"a rotação mais provável é {LABEL[angle]} ({probability:.0%})."
            ),
        )


DETECTOR = Orientation()
