"""Desfoque: energia do Laplaciano junto à tinta (``docs/especificacoes/detectors/blur.md``)."""

from __future__ import annotations

import math

import cv2
import numpy as np

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
        """Média do quadrado do Laplaciano junto à tinta, dividida pelo contraste ao quadrado."""
        y0, y1, x0, x1 = features.core
        gray = page.gray[y0:y1, x0:x1]
        ink = features.ink[y0:y1, x0:x1].astype(np.uint8)
        eligible = features.ink_coverage >= float(params["min_ink_coverage"]) and ink.any()
        if not eligible:
            return Observation({"energy": math.nan}, eligible=False)
        contrast = features.paper_level - float(np.median(page.gray[features.ink]))
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


DETECTOR = Blur()
