"""Bordas pretas nas margens (``docs/especificacoes/detectors/black_borders.md``)."""

from __future__ import annotations

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
from qa_engine.domain.model import (
    Correction,
    CorrectionAction,
    CorrectionClass,
    Region,
    Severity,
)


def _band(lines_dark: NDArray[np.bool_]) -> int:
    """Quantidade de linhas escuras consecutivas a partir da borda."""
    if not lines_dark.size or not lines_dark[0]:
        return 0
    stops = np.flatnonzero(~lines_dark)
    return int(stops[0]) if stops.size else int(lines_dark.size)


_SIDE_PT = {"top": "topo", "bottom": "base", "left": "esquerda", "right": "direita"}


class BlackBorders:
    """Detector de bordas pretas."""

    id = "black_borders"

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Largura da faixa escura contínua em cada lado, em pixels do raster."""
        dark = page.gray < int(params["dark_level"])
        h, w = dark.shape
        need = float(params["dark_fraction"])
        limit_y, limit_x = h // 4, w // 4
        rows = dark.mean(axis=1) >= need
        cols = dark.mean(axis=0) >= need
        bands = {
            "top": _band(rows[:limit_y]),
            "bottom": _band(rows[::-1][:limit_y]),
            "left": _band(cols[:limit_x]),
            "right": _band(cols[::-1][:limit_x]),
        }
        fraction = max(bands["top"] / h, bands["bottom"] / h, bands["left"] / w, bands["right"] / w)
        regions = {
            "top": Region(0, 0, w, bands["top"]),
            "bottom": Region(0, h - bands["bottom"], w, bands["bottom"]),
            "left": Region(0, 0, bands["left"], h),
            "right": Region(w - bands["right"], 0, bands["right"], h),
        }
        side = max(bands, key=lambda s: bands[s] / (h if s in ("top", "bottom") else w))
        return Observation(
            {"fraction": fraction},
            region=regions[side] if bands[side] else None,
            extra={
                "crop_fraction": {
                    s: round(v / (h if s in ("top", "bottom") else w), 4) for s, v in bands.items()
                }
            },
        )

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Sinaliza quando a maior faixa passa de ``min_fraction`` da dimensão."""
        fraction = obs.values["fraction"]
        threshold = float(params["min_fraction"])
        if fraction <= threshold:
            return None
        crop = dict(obs.extra.get("crop_fraction", {}))
        sides = ", ".join(_SIDE_PT[s] for s, v in crop.items() if v)
        return Flag(
            severity=Severity.LOW,
            measure=fraction,
            threshold=threshold,
            confidence=clamp01(0.6 + fraction / (4 * threshold)),
            correction=Correction(
                CorrectionClass.AUTOMATIC,
                CorrectionAction.AUTOCROP,
                "Recortar as bordas pretas na cópia.",
                {"crop_fraction": crop},
            ),
            message=f"Borda preta de {fraction:.1%} ({sides}).",
            region=obs.region,
        )


DETECTOR = BlackBorders()
