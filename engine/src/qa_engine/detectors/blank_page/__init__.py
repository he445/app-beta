"""Página em branco ou quase branca (``docs/especificacoes/detectors/blank_page.md``)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

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
from qa_engine.detectors.features import InkCheck
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity

if TYPE_CHECKING:
    from collections.abc import Mapping

ID = "blank_page"


def ink_check(paper: float, params: Mapping[str, Any] | None) -> InkCheck:
    """Confirmação de tinta das caixas de escrito, com os parâmetros da regra.

    Folha com numeração nunca é branca, mas só conta como numeração a caixa com tinta de
    verdade: o detector de texto também acha a transparência do verso e o gradiente do papel.
    """
    p = params or {}
    return InkCheck(
        paper=paper,
        min_ink=float(p.get("writing_min_ink", 0.01)),
        min_pixels=int(p.get("writing_min_pixels", 30)),
        faint_delta=float(p.get("faint_min_delta", 26)),
    )


class BlankPage:
    """Detector de página em branco."""

    id = ID

    def measure(self, page: PageRaster, features: PageFeatures, params: Params) -> Observation:
        """Cobertura de tinta na área útil e área da maior marca (carimbo, rubrica)."""
        y0, y1, x0, x1 = features.core
        core = features.ink[y0:y1, x0:x1].astype(np.uint8)
        largest = 0
        if core.any():
            _, _, stats, _ = cv2.connectedComponentsWithStats(core, connectivity=8)
            largest = int(stats[1:, cv2.CC_STAT_AREA].max())
        return Observation({"coverage": features.ink_coverage}, extra={"largest_mark": largest})

    def evaluate(self, obs: Observation, baseline: Baseline, params: Params) -> Flag | None:
        """Branca abaixo de ``blank_threshold``; quase branca até ``near_blank_threshold``.

        Folha com numeração (ou qualquer escrito com tinta na região da numeração, mesmo
        riscado) nunca é branca nem quase branca: ela fica no lote e conta na sequência. Só
        traço fraco, sem tinta, deixa a branca para revisão em vez de removê-la.
        """
        if obs.extra.get("numbering_written"):
            return None
        coverage = obs.values["coverage"]
        blank_at = float(params["blank_threshold"])
        near_at = float(params["near_blank_threshold"])
        has_mark = int(obs.extra.get("largest_mark", 0)) >= int(params["mark_min_area"])
        if coverage < blank_at and not has_mark:
            if obs.extra.get("numbering_faint"):
                # Traço fraco sem tinta num canto: pode ser número a lápis claro. Remover uma
                # folha numerada é pior que uma revisão a mais.
                return Flag(
                    severity=Severity.LOW,
                    measure=coverage,
                    threshold=blank_at,
                    confidence=0.5,
                    correction=Correction(
                        CorrectionClass.ESCALATE,
                        CorrectionAction.HUMAN_REVIEW,
                        "Branca com traço fraco num canto (possível número a lápis): confira "
                        "antes de remover.",
                    ),
                    message=f"Página em branco com traço fraco: tinta em {coverage:.2%} da área "
                    "útil.",
                )
            if bool(params["remove_blank_pages"]):
                correction = Correction(
                    CorrectionClass.AUTOMATIC,
                    CorrectionAction.REMOVE_PAGE,
                    "Remover a página em branco da cópia.",
                )
            else:
                correction = Correction(
                    CorrectionClass.ESCALATE,
                    CorrectionAction.HUMAN_REVIEW,
                    "O perfil mantém páginas em branco: confirmar e manter.",
                )
            return Flag(
                severity=Severity.LOW,
                measure=coverage,
                threshold=blank_at,
                confidence=clamp01(1.0 - 0.5 * coverage / blank_at),
                correction=correction,
                message=f"Página em branco: tinta em {coverage:.2%} da área útil.",
            )
        if coverage < near_at:
            return Flag(
                severity=Severity.LOW,
                measure=coverage,
                threshold=near_at,
                confidence=0.5,
                correction=Correction(
                    CorrectionClass.ESCALATE,
                    CorrectionAction.HUMAN_REVIEW,
                    "Quase branca (carimbo, rubrica ou pouco texto): nunca é removida "
                    "automaticamente.",
                ),
                message=f"Página quase branca: tinta em {coverage:.2%} da área útil.",
            )
        return None


DETECTOR = BlankPage()
