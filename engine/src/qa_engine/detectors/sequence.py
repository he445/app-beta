"""Sinalizações de sequência e completude a partir de :mod:`qa_engine.domain.sequencing`.

Produz as regras ``missing_page``, ``out_of_order``, ``numbering_review`` e
``completeness_unverifiable`` (``docs/especificacoes/sequencing.md``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

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
    Gap,
    PageCandidates,
    PageNumberingState,
    SequenceParams,
    SequenceResult,
    document_doubt,
    parse_folio,
    resolve,
)


def implausible(gap: Gap, page_count: int, params: SequenceParams) -> bool:
    """Lacuna maior que o documento (a partir de ``min_implausible_gap``) ou que ``max_gap_sheets``.

    Um número impresso no canto (data, protocolo), lido com confiança, cria um salto assim;
    folha faltando de verdade raramente é mais numerosa que o documento inteiro.
    """
    size = len(gap.missing)
    return size > params.max_gap_sheets or size > max(page_count, params.min_implausible_gap)


def _top_number(page: PageCandidates, params: SequenceParams) -> int | None:
    """Número de folha da leitura mais confiável de uma página com uma só marca não riscada."""
    live = [m for m in page.marks if not m.struck and m.top is not None]
    if len(live) != 1 or live[0].top is None or live[0].top.confidence < params.min_confidence:
        return None
    folio = parse_folio(live[0].top.text)
    return None if folio is None else folio.number


def outliers(
    pages: Sequence[PageCandidates], result: SequenceResult, params: SequenceParams
) -> set[str]:
    """Páginas junto a uma lacuna implausível cuja leitura destoa das duas vizinhas coerentes.

    Exemplo: 20, 1021, 22. A leitura do meio é descartada e o documento é resolvido de novo,
    com o mesmo resolvedor (``domain/sequencing.py`` não muda).
    """
    near = {
        pid
        for gap in result.gaps
        if implausible(gap, len(pages), params)
        for pid in (gap.after_page_id, gap.before_page_id)
    }
    found: set[str] = set()
    for i in range(1, len(pages) - 1):
        page = pages[i]
        if page.page_id not in near:
            continue
        value = _top_number(page, params)
        before, after = _top_number(pages[i - 1], params), _top_number(pages[i + 1], params)
        if value is None or before is None or after is None:
            continue
        if 0 < after - before <= 2 and not before <= value <= after:
            found.add(page.page_id)
    return found


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
    dropped = outliers(pages, result, params)
    readings = {p.page_id: _top_number(p, params) for p in pages if p.page_id in dropped}
    if dropped:
        pages = [PageCandidates(p.page_id) if p.page_id in dropped else p for p in pages]
        result = resolve(pages, params)
        result = replace(
            result,
            pages=tuple(
                replace(p, state=PageNumberingState.AMBIGUOUS) if p.page_id in dropped else p
                for p in result.pages
            ),
        )
    flags: list[SequenceFlag] = []
    doc = Target(TargetKind.DOCUMENT, document_id)
    if result.reordered and any(implausible(g, len(pages), params) for g in result.gaps):
        # Ordem proposta por uma numeração com saltos implausíveis não tem evidência:
        # o documento fica na ordem do arquivo e a numeração vai para revisão.
        file_order = {p.page_id: i for i, p in enumerate(pages)}
        result = replace(
            result,
            pages=tuple(sorted(result.pages, key=lambda p: file_order[p.page_id])),
            order=tuple(p.page_id for p in pages),
            reordered=False,
        )
        flags.append(
            SequenceFlag(
                "numbering_review",
                doc,
                Flag(
                    severity=Severity.MEDIUM,
                    measure=float(sum(implausible(g, len(pages), params) for g in result.gaps)),
                    threshold=0.0,
                    confidence=0.5,
                    correction=Correction(
                        CorrectionClass.ESCALATE,
                        CorrectionAction.HUMAN_REVIEW,
                        "Conferir a numeração na tela de Sequência antes de reordenar.",
                    ),
                    message=(
                        "Numeração lida com saltos implausíveis: a ordem não foi proposta. "
                        "Provavelmente números impressos (datas, códigos) lidos como folha."
                    ),
                ),
            )
        )
    position = {page_id: i + 1 for i, page_id in enumerate(result.order)}
    value_of = {p.page_id: p.value for p in result.pages}

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

    for page_id in sorted(dropped):
        flags.append(
            _review(
                page_id,
                f"Leitura fls. {readings[page_id]} fora da sequência das vizinhas: descartada. "
                "Confira o canto e digite a numeração.",
                0.0,
                0.0,
                Severity.HIGH,
            )
        )

    for gap in result.gaps:
        names = [str(f) for f in gap.missing]
        span = names[0] if len(names) == 1 else f"{names[0]} a {names[-1]}"
        if implausible(gap, len(pages), params):
            # A lista de faltantes tem teto (1000): o salto sai das próprias leituras.
            first, last = value_of[gap.after_page_id], value_of[gap.before_page_id]
            flags.append(
                _review(
                    gap.before_page_id,
                    f"Salto de fls. {first} para {last}: leitura de numeração duvidosa.",
                    float(len(names)),
                    float(params.max_gap_sheets),
                    Severity.HIGH,
                )
            )
            continue
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
        if not numbering.needs_review or numbering.page_id in dropped:
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

    doubt = document_doubt(result, params)
    if doubt is not None:
        span = (
            f"fls. {doubt.first} a {doubt.last}"
            if doubt.first != doubt.last
            else (f"fls. {doubt.first}")
        )
        if doubt.alternative_first is not None and doubt.alternative_last is not None:
            other = (
                f"fls. {doubt.alternative_first} a {doubt.alternative_last}"
                if doubt.alternative_first != doubt.alternative_last
                else f"fls. {doubt.alternative_first}"
            )
            message = (
                f"Numeração do documento inteiro em dúvida: {span} também fecha como {other} "
                f"({doubt.read} lido no lugar de {doubt.alternative}). Confira o documento."
            )
        else:
            message = (
                f"Numeração do documento começa em fls. {doubt.first}, depois de fls. "
                f"{params.max_first_folio}: confira se continua outro volume ou se a "
                "leitura está errada."
            )
        flags.append(_review(doubt.page_id, message, 0.0, 0.0, Severity.HIGH))

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
