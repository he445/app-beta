"""Desfoque: energia do Laplaciano junto à tinta (``docs/especificacoes/detectors/blur.md``)."""

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


class Blur:
    """Detector de desfoque."""

    id = "blur"

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Média do quadrado do Laplaciano junto à tinta, dividida pelo contraste ao quadrado.

        Componentes de tinta sólidos e grandes (faixa preta estreita demais para
        ``black_borders``, tarja, foto) saem da máscara e da mediana do contraste: dentro
        deles o Laplaciano é zero e a mediana vai para o preto.
        """
        y0, y1, x0, x1 = features.core
        gray = page.gray[y0:y1, x0:x1]
        full_ink = without_solid_blocks(
            features.ink,
            float(params.get("solid_min_area", 0.02)),
            float(params.get("solid_min_solidity", 0.9)),
        )
        ink = full_ink[y0:y1, x0:x1].astype(np.uint8)
        eligible = features.ink_coverage >= float(params["min_ink_coverage"]) and ink.any()
        if not eligible:
            return Observation({"energy": math.nan}, eligible=False)
        contrast = features.paper_level - float(np.median(page.gray[full_ink]))
        if contrast < 1.0:
            return Observation({"energy": math.nan}, eligible=False)
        lap = cv2.Laplacian(gray, cv2.CV_64F, ksize=1)
        mask = cv2.dilate(ink, np.ones((3, 3), np.uint8)) > 0
        # Normalizado pelo contraste ao quadrado: página escura ou desbotada não é desfocada.
        energy = float(np.mean(lap[mask] ** 2)) / (contrast * contrast)
        return Observation({"energy": energy})

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Sinaliza quando a energia fica abaixo da fração da mediana do lote."""
        if not obs.eligible:
            return None
        stats = baseline.get("energy")
        if stats is not None and stats.n >= int(params["min_batch_size"]):
            threshold = float(params["relative_threshold"]) * stats.median
            basis = f"{float(params['relative_threshold']):.0%} da mediana do lote"
        else:
            threshold = float(params["absolute_threshold"])
            basis = "limiar absoluto (lote pequeno)"
        energy = obs.values["energy"]
        if energy >= threshold:
            return None
        return Flag(
            severity=Severity.CRITICAL,
            measure=energy,
            threshold=threshold,
            confidence=clamp01(0.5 + 0.5 * (1 - energy / threshold)),
            correction=Correction(
                CorrectionClass.PHYSICAL,
                CorrectionAction.RESCAN,
                "Redigitalizar a folha: a imagem está desfocada.",
            ),
            message=f"Nitidez {energy:.3f} abaixo de {threshold:.3f} ({basis}).",
        )


def without_solid_blocks(
    ink: NDArray[np.bool_], min_area: float, min_solidity: float
) -> NDArray[np.bool_]:
    """Máscara de tinta sem os componentes sólidos e grandes.

    Args:
        ink: máscara de tinta da página.
        min_area: fração da página a partir da qual um componente é grande.
        min_solidity: área do componente sobre a da envoltória convexa a partir da qual ele
            é sólido (faixa, tarja), não escrita.
    """
    count, labels, stats, _ = cv2.connectedComponentsWithStats(ink.astype(np.uint8), 8)
    limit = min_area * ink.size
    big = [i for i in range(1, count) if stats[i, cv2.CC_STAT_AREA] >= limit]
    if not big:
        return ink
    out = ink.copy()
    for i in big:
        component = (labels == i).astype(np.uint8)
        contours, _ = cv2.findContours(component, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        hull = cv2.contourArea(cv2.convexHull(np.vstack(contours))) if contours else 0.0
        if hull > 0 and stats[i, cv2.CC_STAT_AREA] / hull >= min_solidity:
            out[labels == i] = False
    return out


DETECTOR = Blur()
