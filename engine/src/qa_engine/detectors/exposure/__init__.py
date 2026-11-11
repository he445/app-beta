"""Página escura, clara ou sem contraste (``docs/especificacoes/detectors/exposure.md``)."""

from __future__ import annotations

import math

import numpy as np

from qa_engine.detectors.base import (
    Baseline,
    Flag,
    Observation,
    PageFeatures,
    PageRaster,
    Params,
    Stats,
    clamp01,
)
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity


class Exposure:
    """Detector de exposição: brilho do papel e contraste papel-tinta."""

    id = "exposure"

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Brilho do papel (percentil 90) e contraste (papel menos mediana da tinta)."""
        ink = features.ink
        if int(ink.sum()) < int(params["min_ink_pixels"]):
            nan = math.nan
            return Observation({"paper": nan, "contrast": nan}, eligible=False)
        ink_level = float(np.median(page.gray[ink]))
        return Observation(
            {"paper": features.paper_level, "contrast": features.paper_level - ink_level}
        )

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Escore z robusto contra o lote; em lote pequeno, contra a referência do perfil."""
        if not obs.eligible:
            return None
        k = float(params["z_threshold"])
        min_batch = int(params["min_batch_size"])
        paper = _stats(baseline.get("paper"), min_batch, params, "paper")
        contrast = _stats(baseline.get("contrast"), min_batch, params, "contrast")
        z_paper = (obs.values["paper"] - paper.median) / paper.sigma
        z_contrast = (obs.values["contrast"] - contrast.median) / contrast.sigma
        low_contrast = z_contrast < -k
        if abs(z_paper) <= k and not low_contrast:
            return None
        if low_contrast:
            kind = "sem contraste"
            correction = Correction(
                CorrectionClass.PHYSICAL,
                CorrectionAction.RESCAN,
                "Redigitalizar com outra exposição ou em escala de cinza; clarear página "
                "ilegível é correção proibida.",
            )
        else:
            kind = "escura" if z_paper < 0 else "clara"
            correction = Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.AUTO_LEVELS,
                "Aplicar auto-níveis na cópia.",
            )
        measure = max(abs(z_paper), -z_contrast)
        return Flag(
            severity=Severity.HIGH,
            measure=measure,
            threshold=k,
            confidence=clamp01(0.5 + (measure - k) / (2 * k)),
            correction=correction,
            message=(
                f"Página {kind}: papel {obs.values['paper']:.0f} (z={z_paper:+.1f}), "
                f"contraste {obs.values['contrast']:.0f} (z={z_contrast:+.1f})."
            ),
        )


def _stats(stats: Stats | None, min_batch: int, params: Params, key: str) -> Stats:
    floor = float(params[f"min_sigma_{key}"])
    if stats is None or stats.n < min_batch:
        return Stats(float(params[f"reference_{key}"]), floor, 0)
    return Stats(stats.median, max(stats.sigma, floor), stats.n)


DETECTOR = Exposure()
