"""Caso de uso ApplyCorrection: aplica correções automáticas numa cópia (princípio 2).

O original nunca é alterado. A versão corrigida de uma página é sempre o
original com **todas** as correções de imagem decididas (``correct``),
aplicadas numa ordem canônica que não depende da ordem das decisões
(``docs/especificacoes/corrections.md``). Cada versão gravada vira um evento no log só de
inserção da porta ``PageVersionStore``; a cópia é reanalisada pelos detectores
de página antes de ir para a saída.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from qa_engine.application.profile import Profile
from qa_engine.application.serialize import iso
from qa_engine.detectors.base import ANALYSIS_DPI, PageRaster, Stats
from qa_engine.detectors.features import compute_features
from qa_engine.detectors.registry import PAGE_DETECTORS
from qa_engine.domain.model import (
    CorrectionAction,
    CorrectionClass,
    DecisionAction,
    Finding,
    TargetKind,
)
from qa_engine.ports import PageVersionStore, as_u8

IMAGE_ACTIONS = {
    CorrectionAction.DESKEW,
    CorrectionAction.ROTATE,
    CorrectionAction.MIRROR,
    CorrectionAction.AUTOCROP,
    CorrectionAction.DESPECKLE,
    CorrectionAction.AUTO_LEVELS,
    CorrectionAction.TO_GRAYSCALE,
}

CANONICAL_ORDER: tuple[CorrectionAction, ...] = (
    CorrectionAction.AUTOCROP,
    CorrectionAction.ROTATE,
    CorrectionAction.MIRROR,
    CorrectionAction.DESKEW,
    CorrectionAction.DESPECKLE,
    CorrectionAction.AUTO_LEVELS,
    CorrectionAction.TO_GRAYSCALE,
)
"""Ordem de aplicação. O recorte vem primeiro porque as frações foram medidas no
original; endireitar depois de recortar não desloca as bordas já removidas."""


def transform(
    img: NDArray[np.uint8], action: CorrectionAction, params: Mapping[str, Any]
) -> NDArray[np.uint8]:
    """Aplica a transformação de imagem de uma correção automática."""
    return as_u8(_transform(img, action, params))


class CorrectionNotApplicableError(ValueError):
    """A sinalização não tem correção automática de imagem."""


@dataclass(frozen=True, slots=True)
class AppliedCorrection:
    """Registro de uma versão corrigida gravada para uma página."""

    page_id: str
    finding_ids: tuple[str, ...]
    """Sinalizações que motivaram este evento."""
    chain: tuple[str, ...]
    """Todas as sinalizações aplicadas na versão, em ordem canônica."""
    output: str | None
    """Nome do arquivo da versão (``None`` = sem correção: vale o original)."""
    output_sha256: str | None
    source_sha256: str
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


def is_image_correction(finding: Finding) -> bool:
    """Correção automática de imagem numa página."""
    return (
        finding.correction.kind is CorrectionClass.AUTOMATIC
        and finding.correction.action in IMAGE_ACTIONS
        and finding.target.kind is TargetKind.PAGE
    )


def canonical_chain(findings: Iterable[Finding]) -> list[Finding]:
    """Correções de imagem sem repetição, na ordem canônica (empate: identificador)."""
    unique = {f.id: f for f in findings if is_image_correction(f)}
    return sorted(
        unique.values(),
        key=lambda f: (CANONICAL_ORDER.index(f.correction.action), f.id),
    )


def active_chain(findings: Iterable[Finding], page_id: str) -> list[Finding]:
    """Correções de imagem decididas como ``correct`` numa página, em ordem canônica."""
    return canonical_chain(
        f
        for f in findings
        if f.target.id == page_id
        and f.decision is not None
        and f.decision.action is DecisionAction.CORRECT
    )


def render_chain(original: NDArray[np.uint8], chain: Sequence[Finding]) -> NDArray[np.uint8]:
    """Aplica a cadeia ao original, sem nunca alterá-lo."""
    image = original
    for finding in chain:
        image = transform(image, finding.correction.action, finding.correction.params)
    return image


def describe_correction(action: CorrectionAction | str, params: Mapping[str, Any]) -> str:
    """Texto curto para o revisor: "endireitada 2,3°", "bordas recortadas"."""
    action = CorrectionAction(action)
    if action is CorrectionAction.DESKEW:
        angle = abs(float(params.get("skew_deg", 0.0)))
        return f"endireitada {angle:.1f}°".replace(".", ",")
    if action is CorrectionAction.ROTATE:
        return f"girada {int(params.get('angle_deg', 0)) % 360}°"
    return {
        CorrectionAction.MIRROR: "espelhada",
        CorrectionAction.AUTOCROP: "bordas pretas recortadas",
        CorrectionAction.DESPECKLE: "pontilhado removido",
        CorrectionAction.AUTO_LEVELS: "brilho e contraste ajustados",
        CorrectionAction.TO_GRAYSCALE: "convertida para cinza",
    }.get(action, action.value)


def current_version(store: PageVersionStore, page_id: str, chain_ids: Sequence[str]) -> str | None:
    """Nome da versão gravada mais recente cuja cadeia é exatamente ``chain_ids``.

    Returns:
        O nome do arquivo, ou ``None`` se não há versão gravada para essa cadeia
        (ou se a cadeia é vazia: vale o original).
    """
    wanted = list(chain_ids)
    if not wanted:
        return None
    for event in reversed(store.events()):
        if event.get("page_id") != page_id:
            continue
        if [c["finding_id"] for c in event["chain"]] == wanted and event.get("output"):
            name: str = event["output"]
            return name
    return None


def refresh_page(
    *,
    store: PageVersionStore,
    page_id: str,
    chain: Sequence[Finding],
    load_original: Callable[[], NDArray[np.uint8]],
    dpi: float | None,
    source_sha256: str,
    profile: Profile,
    baselines: Mapping[str, Mapping[str, Stats]],
    now: datetime,
    event: str,
    finding_ids: Sequence[str],
    reviewer: str,
    operation_id: str | None = None,
) -> AppliedCorrection:
    """Garante que a versão corrigida da página corresponde à cadeia e registra o evento.

    Reaproveita uma versão já gravada para a mesma cadeia (desfazer volta ao
    mesmo arquivo); senão renderiza a cadeia sobre o original e reanalisa.

    Args:
        store: versões e log da página.
        page_id: página.
        chain: correções ativas depois da mudança, em ordem canônica.
        load_original: lê o original (só chamado se for preciso renderizar).
        dpi: resolução do raster original.
        source_sha256: SHA-256 do arquivo original.
        profile: perfil do lote (reanálise).
        baselines: linhas de base do lote (reanálise).
        now: horário do evento.
        event: ``applied``, ``undone`` ou ``refreshed``.
        finding_ids: sinalizações que mudaram neste evento.
        reviewer: quem decidiu.
        operation_id: operação em lote, se houver.
    """
    ids = [f.id for f in chain]
    output = current_version(store, page_id, ids)
    sha: str | None = None
    remaining: tuple[str, ...] = ()
    if chain:
        image = store.load(output) if output else None
        if image is None:
            image = render_chain(load_original(), chain)
            output, sha = store.save(page_id, image, dpi)
        else:
            sha = next(
                (
                    e.get("output_sha256")
                    for e in reversed(store.events())
                    if e.get("output") == output
                ),
                None,
            )
        remaining = reanalyze(image, dpi, profile, baselines)
    stored = store.append(
        {
            "event": event,
            "page_id": page_id,
            "finding_ids": list(finding_ids),
            "chain": [
                {
                    "finding_id": f.id,
                    "action": f.correction.action.value,
                    "params": dict(f.correction.params),
                }
                for f in chain
            ],
            "output": output if chain else None,
            "output_sha256": sha,
            "source_sha256": source_sha256,
            "operation_id": operation_id,
            "reviewer": reviewer,
            "at": iso(now),
            "remaining_rules": list(remaining),
        }
    )
    return AppliedCorrection(
        page_id=page_id,
        finding_ids=tuple(finding_ids),
        chain=tuple(ids),
        output=stored["output"],
        output_sha256=sha,
        source_sha256=source_sha256,
        applied_at=now,
        remaining_rules=remaining,
    )


def apply_correction(
    *,
    finding: Finding,
    original: NDArray[np.uint8],
    dpi: float | None,
    source_sha256: str,
    store: PageVersionStore,
    profile: Profile,
    baselines: Mapping[str, Mapping[str, Stats]],
    now: datetime,
    active: Sequence[Finding] = (),
    reviewer: str = "revisor",
    operation_id: str | None = None,
) -> AppliedCorrection:
    """Aplica a correção proposta de ``finding`` numa cópia e registra no log.

    Args:
        finding: sinalização com correção automática de imagem.
        original: página original em resolução de captura.
        dpi: resolução do original.
        source_sha256: SHA-256 do arquivo original.
        store: versões corrigidas do lote.
        profile: perfil do lote.
        baselines: linhas de base do lote.
        now: horário da decisão.
        active: outras correções de imagem já aplicadas na página.
        reviewer: quem decidiu.
        operation_id: operação em lote, se houver.

    Raises:
        CorrectionNotApplicableError: se a correção não for automática de imagem.
    """
    if not is_image_correction(finding):
        correction = finding.correction
        raise CorrectionNotApplicableError(
            f"{finding.rule}: correção {correction.kind.value}/{correction.action.value} "
            "não é aplicável automaticamente na imagem"
        )
    return refresh_page(
        store=store,
        page_id=finding.target.id,
        chain=canonical_chain([*active, finding]),
        load_original=lambda: original,
        dpi=dpi,
        source_sha256=source_sha256,
        profile=profile,
        baselines=baselines,
        now=now,
        event="applied",
        finding_ids=[finding.id],
        reviewer=reviewer,
        operation_id=operation_id,
    )
