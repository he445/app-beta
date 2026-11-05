"""Resolução abaixo do exigido pelo perfil (``spec/detectors/low_resolution.md``)."""

from __future__ import annotations

import math

from qa_engine.detectors.base import Baseline, Flag, Observation, PageFeatures, PageRaster, Params
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity


class LowResolution:
    """Detector de resolução gravada abaixo do mínimo."""

    id = "low_resolution"

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """DPI gravado no arquivo (``nan`` quando ausente)."""
        return Observation({"dpi": page.dpi if page.dpi is not None else math.nan})

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Compara com ``min_dpi``; DPI ausente vira revisão humana de baixa confiança."""
        dpi = obs.values["dpi"]
        minimum = float(params["min_dpi"])
        if math.isnan(dpi):
            return Flag(
                severity=Severity.HIGH,
                measure=0.0,
                threshold=minimum,
                confidence=0.3,
                correction=Correction(
                    CorrectionClass.ESCALATE,
                    CorrectionAction.HUMAN_REVIEW,
                    "Conferir a configuração do scanner: o arquivo não grava a resolução.",
                ),
                message="Resolução não gravada no arquivo.",
            )
        if dpi >= minimum - 0.5:
            return None
        return Flag(
            severity=Severity.HIGH,
            measure=dpi,
            threshold=minimum,
            confidence=1.0,
            correction=Correction(
                CorrectionClass.PHYSICAL,
                CorrectionAction.RESCAN,
                f"Reconfigurar o scanner para {minimum:.0f} dpi e redigitalizar. "
                "Aumentar a resolução por interpolação é correção proibida.",
                {"dpi": minimum},
            ),
            message=f"Resolução de {dpi:.0f} dpi, abaixo do mínimo de {minimum:.0f} dpi.",
        )


DETECTOR = LowResolution()
