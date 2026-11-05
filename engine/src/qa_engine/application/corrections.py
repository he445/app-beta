"""Caso de uso ApplyCorrection: aplica uma correção automática numa cópia (princípio 2).

O original nunca é alterado. Cada aplicação grava um arquivo novo e uma linha
em ``corrections.jsonl`` com o que foi feito; a cópia é reanalisada pelos
detectores de página antes de ir para a saída.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image

from qa_engine.application.profile import Profile
from qa_engine.application.serialize import iso
from qa_engine.detectors.base import ANALYSIS_DPI, PageRaster, Stats
from qa_engine.detectors.features import compute_features
from qa_engine.detectors.registry import PAGE_DETECTORS
from qa_engine.domain.model import CorrectionAction, CorrectionClass, Finding
from qa_engine.ports import as_u8

IMAGE_ACTIONS = {
    CorrectionAction.DESKEW,
    CorrectionAction.ROTATE,
    CorrectionAction.MIRROR,
    CorrectionAction.AUTOCROP,
    CorrectionAction.DESPECKLE,
    CorrectionAction.AUTO_LEVELS,
    CorrectionAction.TO_GRAYSCALE,
}


def transform(
    img: NDArray[np.uint8], action: CorrectionAction, params: Mapping[str, Any]
) -> NDArray[np.uint8]:
    """Aplica a transformação de imagem de uma correção automática."""
    return as_u8(_transform(img, action, params))


class CorrectionNotApplicableError(ValueError):
    """A sinalização não tem correção automática de imagem."""


@dataclass(frozen=True, slots=True)
class AppliedCorrection:
    """Registro de uma correção aplicada."""

    finding_id: str
    page_id: str
    action: str
    params: Mapping[str, Any]
    source_sha256: str
    output: Path
    output_sha256: str
    applied_at: datetime
    remaining_rules: tuple[str, ...]
    """Regras que ainda disparam na cópia corrigida."""


def _white(img: NDArray[np.uint8]) -> int | tuple[int, int, int]:
    return 255 if img.ndim == 2 else (255, 255, 255)


def _transform(img: NDArray[np.uint8], action: CorrectionAction, params: Mapping[str, Any]) -> Any:
    if action is CorrectionAction.DESKEW:
        angle = float(params["skew_deg"])
        h, w = img.shape[:2]
        matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)
        return cv2.warpAffine(img, matrix, (w, h), flags=cv2.INTER_CUBIC, borderValue=_white(img))
    if action is CorrectionAction.ROTATE:
        turns = {
            90: cv2.ROTATE_90_CLOCKWISE,
            180: cv2.ROTATE_180,
            270: cv2.ROTATE_90_COUNTERCLOCKWISE,
        }
        return cv2.rotate(img, turns[int(params["angle_deg"]) % 360])
    if action is CorrectionAction.MIRROR:
        return cv2.flip(img, 1)
    if action is CorrectionAction.AUTOCROP:
        crop = params["crop_fraction"]
        h, w = img.shape[:2]
        top, bottom = round(crop["top"] * h), round(crop["bottom"] * h)
        left, right = round(crop["left"] * w), round(crop["right"] * w)
        return np.ascontiguousarray(img[top : h - bottom, left : w - right])
    if action is CorrectionAction.DESPECKLE:
        return cv2.medianBlur(img, 3)
    if action is CorrectionAction.AUTO_LEVELS:
        lo, hi = np.percentile(img, (1, 99))
        if hi - lo < 1:
            return img
        stretched = (img.astype(np.float32) - lo) * (255.0 / (hi - lo))
        return np.clip(stretched, 0, 255).astype(np.uint8)
    if action is CorrectionAction.TO_GRAYSCALE:
        return img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    raise CorrectionNotApplicableError(f"ação {action.value} não é transformação de imagem")


def reanalyze(
    img: NDArray[np.uint8],
    dpi: float | None,
    profile: Profile,
    baselines: Mapping[str, Mapping[str, Stats]],
) -> tuple[str, ...]:
    """Regras de página que ainda disparam numa imagem corrigida."""
    gray = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    scale = ANALYSIS_DPI / dpi if dpi else 1240 / min(gray.shape)
    size = (max(1, round(gray.shape[1] * scale)), max(1, round(gray.shape[0] * scale)))
    small = cv2.resize(gray, size, interpolation=cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR)
    raster = PageRaster(small, scale, dpi)
    features = compute_features(small)
    remaining: list[str] = []
    for detector in PAGE_DETECTORS:
        if not profile.enabled(detector.id):
            continue
        params = profile.params(detector.id)
        obs = detector.measure(raster, features, params)
        if detector.evaluate(obs, baselines.get(detector.id, {}), params) is not None:
            remaining.append(detector.id)
    return tuple(remaining)


def apply_correction(
    *,
    finding: Finding,
    original: NDArray[np.uint8],
    dpi: float | None,
    source_sha256: str,
    out_dir: Path,
    profile: Profile,
    baselines: Mapping[str, Mapping[str, Stats]],
    now: datetime,
) -> AppliedCorrection:
    """Aplica a correção proposta de ``finding`` numa cópia e registra no log.

    Raises:
        CorrectionNotApplicableError: se a correção não for automática de imagem.
    """
    correction = finding.correction
    if correction.kind is not CorrectionClass.AUTOMATIC or correction.action not in IMAGE_ACTIONS:
        raise CorrectionNotApplicableError(
            f"{finding.rule}: correção {correction.kind.value}/{correction.action.value} "
            "não é aplicável automaticamente na imagem"
        )
    corrected = transform(original, correction.action, correction.params)
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / f"{finding.target.id}.{correction.action.value}.png"
    image = Image.fromarray(corrected)
    image.save(output, dpi=(dpi, dpi) if dpi else None)
    output_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    remaining = reanalyze(corrected, dpi, profile, baselines)
    record = AppliedCorrection(
        finding_id=finding.id,
        page_id=finding.target.id,
        action=correction.action.value,
        params=dict(correction.params),
        source_sha256=source_sha256,
        output=output,
        output_sha256=output_sha,
        applied_at=now,
        remaining_rules=remaining,
    )
    with (out_dir / "corrections.jsonl").open("a", encoding="utf-8") as log:
        log.write(
            json.dumps(
                {
                    "finding_id": record.finding_id,
                    "page_id": record.page_id,
                    "action": record.action,
                    "params": record.params,
                    "source_sha256": record.source_sha256,
                    "output": output.name,
                    "output_sha256": record.output_sha256,
                    "applied_at": iso(now),
                    "remaining_rules": list(remaining),
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    return record
