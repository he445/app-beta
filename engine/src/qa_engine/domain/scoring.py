"""Estado do documento, veredito do lote e amostragem dos verdes.

Implementa ``docs/especificacoes/scoring.md``. Funções puras, sem E/S.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from qa_engine.domain.model import (
    DecisionAction,
    DocumentState,
    Finding,
    Severity,
    TargetKind,
    Verdict,
)


@dataclass(frozen=True, slots=True)
class VerdictPolicy:
    """Limites do veredito, configuráveis por perfil."""

    max_yellow_ratio: float = 0.02
    green_sample_ratio: float = 0.05


def document_state(findings: Iterable[Finding]) -> DocumentState:
    """Estado do documento pelo pior defeito pendente.

    Verde: nenhuma pendência acima de baixo. Amarelo: médio ou alto pendente.
    Vermelho: crítico pendente.
    """
    worst = -1
    for finding in findings:
        if finding.pending:
            worst = max(worst, finding.severity.rank)
    if worst >= Severity.CRITICAL.rank:
        return DocumentState.RED
    if worst >= Severity.MEDIUM.rank:
        return DocumentState.YELLOW
    return DocumentState.GREEN


def findings_by_document(
    findings: Iterable[Finding],
    page_to_document: Mapping[str, str],
) -> dict[str, list[Finding]]:
    """Agrupa sinalizações de página e de documento pelo documento a que pertencem."""
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        if finding.target.kind is TargetKind.PAGE:
            doc = page_to_document.get(finding.target.id)
        elif finding.target.kind is TargetKind.DOCUMENT:
            doc = finding.target.id
        else:
            doc = None
        if doc is not None:
            grouped.setdefault(doc, []).append(finding)
    return grouped


def batch_verdict(
    states: Mapping[str, DocumentState],
    findings: Iterable[Finding],
    policy: VerdictPolicy,
) -> Verdict:
    """Veredito do lote.

    Reprovado com qualquer vermelho pendente; aprovado sem vermelhos, com no
    máximo ``max_yellow_ratio`` de amarelos e sem defeitos de origem nem
    sinalizações de lote pendentes; aprovado com ressalvas nos demais casos.
    """
    if not states:
        return Verdict.APPROVED_WITH_RESERVATIONS
    values = list(states.values())
    if DocumentState.RED in values:
        return Verdict.REJECTED
    findings = list(findings)
    batch_pending = any(
        f.target.kind is TargetKind.BATCH and f.pending and f.severity.rank >= Severity.MEDIUM.rank
        for f in findings
    )
    source_defects = any(
        f.decision is not None and f.decision.action is DecisionAction.SOURCE_DEFECT
        for f in findings
    )
    yellow_ratio = values.count(DocumentState.YELLOW) / len(values)
    if yellow_ratio <= policy.max_yellow_ratio and not source_defects and not batch_pending:
        return Verdict.APPROVED
    return Verdict.APPROVED_WITH_RESERVATIONS


def green_sample(batch_id: str, green_document_ids: Sequence[str], ratio: float) -> list[str]:
    """Amostra determinística dos documentos verdes para revisão humana.

    Ordena pelo SHA-256 de ``batch_id/document_id`` e pega os primeiros
    ``ceil(ratio * n)``. Sem aleatoriedade: a mesma entrada dá a mesma amostra.
    """
    if ratio <= 0 or not green_document_ids:
        return []
    size = math.ceil(ratio * len(green_document_ids))
    ranked = sorted(
        green_document_ids,
        key=lambda d: hashlib.sha256(f"{batch_id}/{d}".encode()).hexdigest(),
    )
    return sorted(ranked[:size])


def pages_needing_review(
    page_ids: Sequence[str],
    findings: Iterable[Finding],
    page_to_document: Mapping[str, str],
    sampled_documents: Iterable[str],
) -> set[str]:
    """Páginas que exigem olho humano.

    Uma página exige revisão se tem sinalização de severidade médio ou acima,
    se pertence a um documento com sinalização de documento médio ou acima, ou
    se pertence a um documento sorteado na amostragem dos verdes. Sinalizações
    baixas são tratadas em massa e não contam.
    """
    review: set[str] = set()
    flagged_docs: set[str] = set(sampled_documents)
    for finding in findings:
        if finding.severity.rank < Severity.MEDIUM.rank:
            continue
        if finding.target.kind is TargetKind.PAGE:
            review.add(finding.target.id)
        elif finding.target.kind is TargetKind.DOCUMENT:
            flagged_docs.add(finding.target.id)
    for page in page_ids:
        if page_to_document.get(page) in flagged_docs:
            review.add(page)
    return review
