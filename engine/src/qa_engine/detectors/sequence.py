"""Sinalizações de sequência e completude a partir de :mod:`qa_engine.domain.sequencing`.

Produz as regras ``missing_page``, ``out_of_order``, ``numbering_review`` e
``completeness_unverifiable`` (``docs/especificacoes/sequencing.md``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from qa_engine.detectors.base import Flag
from qa_engine.domain.model import (
    Correction,
    CorrectionAction,
    CorrectionClass,
    Severity,
    Target,
    TargetKind,
)
from qa_engine.domain.sequencing import (
    PageCandidates,
    PageNumberingState,
    SequenceParams,
    SequenceResult,
    resolve,
)


@dataclass(frozen=True, slots=True)
class SequenceFlag:
    """Uma sinalização de sequência com regra e alvo."""

    rule: str
    target: Target
    flag: Flag


def _review(
    page_id: str, message: str, measure: float, threshold: float, severity: Severity
) -> SequenceFlag:
    return SequenceFlag(
        "numbering_review",
        Target(TargetKind.PAGE, page_id),
        Flag(
            severity=severity,
            measure=measure,
            threshold=threshold,
            confidence=0.5,
            correction=Correction(
                CorrectionClass.ESCALATE,
                CorrectionAction.HUMAN_REVIEW,
                "Conferir o canto ampliado e digitar a numeração correta (tecla N).",
            ),
            message=message,
        ),
    )


def analyze_document(
    document_id: str,
    pages: Sequence[PageCandidates],
    params: SequenceParams,
    declared_count: int | None = None,
    duplicates: Mapping[str, str] | None = None,
) -> tuple[SequenceResult, list[SequenceFlag]]:
    """Resolve a numeração de um documento e gera as sinalizações.

    Args:
        document_id: identificador do documento.
        pages: candidatos de numeração por página, na ordem do arquivo.
        params: parâmetros do resolvedor, vindos do perfil.
        declared_count: contagem declarada no manifesto do lote, se houver.
        duplicates: cópia → original das duplicatas já sinalizadas. A cópia não
            participa da sequência, e numeração repetida no par não gera uma
            segunda sinalização.
    """
    duplicates = duplicates or {}
    paired = set(duplicates) | set(duplicates.values())
    pages = [PageCandidates(p.page_id) if p.page_id in duplicates else p for p in pages]
    result = resolve(pages, params)
    flags: list[SequenceFlag] = []
    doc = Target(TargetKind.DOCUMENT, document_id)
    position = {page_id: i + 1 for i, page_id in enumerate(result.order)}

    if result.reordered:
        flags.append(
            SequenceFlag(
                "out_of_order",
                doc,
                Flag(
                    severity=Severity.MEDIUM,
                    measure=float(
                        sum(a != b.page_id for a, b in zip(result.order, pages, strict=True))
                    ),
                    threshold=0.0,
                    confidence=params.high_confidence,
                    correction=Correction(
                        CorrectionClass.AUTOMATIC,
                        CorrectionAction.REORDER,
                        "Reordenar as páginas pela numeração (antes e depois na tela).",
                        {"order": list(result.order)},
                    ),
                    message="Páginas fora de ordem pela numeração lida.",
                ),
            )
        )

    for gap in result.gaps:
        names = [str(f) for f in gap.missing]
        span = names[0] if len(names) == 1 else f"{names[0]} a {names[-1]}"
        if not gap.confirmed:
            flags.append(
                _review(
                    gap.before_page_id,
                    f"Possível lacuna (fls. {span}) com leitura duvidosa de um dos lados.",
                    float(len(names)),
                    0.0,
                    Severity.HIGH,
                )
            )
            continue
        only_backs = all(f.verso for f in gap.missing)
        flags.append(
            SequenceFlag(
                "missing_page",
                doc,
                Flag(
                    severity=Severity.CRITICAL,
                    measure=float(len(names)),
                    threshold=0.0,
                    confidence=params.high_confidence,
                    correction=Correction(
                        CorrectionClass.PHYSICAL,
                        CorrectionAction.RESCAN_BACK
                        if only_backs
                        else CorrectionAction.LOCATE_SHEET,
                        (
                            f"Digitalizar o verso esquecido (fls. {span})."
                            if only_backs
                            else f"Localizar fls. {span} no original, redigitalizar e inserir "
                            f"depois da posição {position[gap.after_page_id]}."
                        ),
                        {
                            "after_page_id": gap.after_page_id,
                            "before_page_id": gap.before_page_id,
                            "missing": names,
                        },
                    ),
                    message=f"Falta fls. {span}." if len(names) == 1 else f"Faltam fls. {span}.",
                ),
            )
        )

    for page_id in result.repeated:
        if page_id in paired:
            continue
        flags.append(
            _review(
                page_id,
                "Numeração repetida: duplicata ou defeito de origem.",
                0.0,
                0.0,
                Severity.HIGH,
            )
        )

    for numbering in result.pages:
        if not numbering.needs_review:
            continue
        severity = (
            Severity.MEDIUM if numbering.state is PageNumberingState.INFERRED else Severity.HIGH
        )
        guess = f"; valor assumido {numbering.value}" if numbering.value else ""
        label = {
            PageNumberingState.INFERRED: "Numeração inferida pelo contexto",
            PageNumberingState.AMBIGUOUS: "Mais de um número sem risco",
            PageNumberingState.ILLEGIBLE: "Numeração ilegível",
        }[numbering.state]
        flags.append(
            _review(
                numbering.page_id,
                f"{label}{guess}.",
                numbering.confidence,
                params.min_confidence,
                severity,
            )
        )

    if declared_count is not None and len(pages) < declared_count:
        short = declared_count - len(pages)
        flags.append(
            SequenceFlag(
                "missing_page",
                doc,
                Flag(
                    severity=Severity.CRITICAL,
                    measure=float(short),
                    threshold=0.0,
                    confidence=0.9,
                    correction=Correction(
                        CorrectionClass.PHYSICAL,
                        CorrectionAction.LOCATE_SHEET,
                        f"Localizar {short} folha(s) no original e redigitalizar.",
                        {"declared": declared_count, "found": len(pages)},
                    ),
                    message=f"Contagem declarada {declared_count}, encontradas {len(pages)}.",
                ),
            )
        )
    elif declared_count is None and not result.has_numbering:
        flags.append(
            SequenceFlag(
                "completeness_unverifiable",
                doc,
                Flag(
                    severity=Severity.LOW,
                    measure=0.0,
                    threshold=0.0,
                    confidence=1.0,
                    correction=Correction(
                        CorrectionClass.ESCALATE,
                        CorrectionAction.HUMAN_REVIEW,
                        "Sem numeração nem contagem declarada: incluir a contagem no "
                        "manifesto da preparação do lote.",
                    ),
                    message="Completude não verificável.",
                ),
            )
        )
    return result, flags
