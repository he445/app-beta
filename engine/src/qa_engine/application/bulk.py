"""Classificação do "Corrigir tudo" (``docs/especificacoes/corrections.md``).

Só entra o que é automático e seguro: correções de imagem na cópia, remoção
de página em branco e reordenação pela numeração. Ficam pendentes, com o
motivo: página faltando (aprovação manual), defeitos que exigem
redigitalizar (nunca "melhorados" por software) e o que pede decisão humana,
como duplicatas (``docs/visao-geral/casos-de-borda.md``).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from qa_engine.application.corrections import IMAGE_ACTIONS
from qa_engine.domain.model import CorrectionAction, CorrectionClass

AUTO_ACTIONS = frozenset({*IMAGE_ACTIONS, CorrectionAction.REMOVE_PAGE, CorrectionAction.REORDER})
"""Ações que o "Corrigir tudo" decide como ``correct``."""

MISSING_PAGE_RULES = frozenset({"missing_page"})
MANUAL_ONLY_RULES = frozenset({"duplicate_page"})
"""Duas vias legítimas existem: duplicata nunca é removida automaticamente."""

RESCAN_RULES = frozenset(
    {"blur", "low_resolution", "corrupted_file", "cropped_content", "truncated_image"}
)
"""Defeitos cuja única correção é redigitalizar (inclui regras ainda não implementadas)."""


class SkipCategory:
    """Categorias do que o "Corrigir tudo" deixa pendente."""

    MISSING_PAGE = "missing_page"
    NEEDS_RESCAN = "needs_rescan"
    MANUAL = "manual"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class BulkUnit:
    """Unidade de progresso: uma página (ou um documento, na reordenação)."""

    label: str
    page_id: str | None
    findings: tuple[Mapping[str, Any], ...]
    """Sinalizações decididas como ``correct`` nesta unidade."""
    image_findings: tuple[Mapping[str, Any], ...]
    """As que exigem gravar uma versão corrigida da página."""


@dataclass(frozen=True, slots=True)
class BulkPlan:
    """O que a operação vai aplicar e o que vai deixar pendente."""

    units: tuple[BulkUnit, ...]
    skipped: tuple[dict[str, Any], ...]

    @property
    def total(self) -> int:
        """Total de unidades (páginas e documentos) a corrigir."""
        return len(self.units)


def skip_entry(finding: Mapping[str, Any], category: str, reason: str) -> dict[str, Any]:
    """Item de ``result.skipped`` (``bulk-correction.schema.json``)."""
    return {
        "finding_id": finding["id"],
        "rule": finding["rule"],
        "severity": finding["severity"],
        "target": dict(finding["target"]),
        "category": category,
        "reason": reason,
    }


def skip_reason(finding: Mapping[str, Any]) -> tuple[str, str]:
    """Por que uma sinalização pendente não é corrigida automaticamente."""
    correction = finding["correction"]
    if finding["rule"] in MISSING_PAGE_RULES:
        return (
            SkipCategory.MISSING_PAGE,
            "Página faltando: exige aprovação manual (retrabalho, defeito de origem ou "
            "aprovar mesmo assim).",
        )
    if finding["rule"] in RESCAN_RULES or correction["kind"] == CorrectionClass.PHYSICAL.value:
        return (
            SkipCategory.NEEDS_RESCAN,
            f"Precisa redigitalizar: {correction['description']}",
        )
    if finding["rule"] in MANUAL_ONLY_RULES:
        return (
            SkipCategory.MANUAL,
            "Duplicata nunca é removida automaticamente: duas vias podem ser legítimas.",
        )
    return SkipCategory.MANUAL, f"Exige decisão humana: {correction['description']}"


def is_automatic(finding: Mapping[str, Any]) -> bool:
    """Se a sinalização entra no "Corrigir tudo"."""
    correction = finding["correction"]
    if correction["kind"] != CorrectionClass.AUTOMATIC.value:
        return False
    if finding["rule"] in MANUAL_ONLY_RULES | MISSING_PAGE_RULES | RESCAN_RULES:
        return False
    action = CorrectionAction(correction["action"])
    if action not in AUTO_ACTIONS:
        return False
    if action in IMAGE_ACTIONS or action is CorrectionAction.REMOVE_PAGE:
        return bool(finding["target"]["kind"] == "page")
    return bool(finding["target"]["kind"] == "document")


def plan_bulk(report: Mapping[str, Any], scope_kind: str, scope_id: str) -> BulkPlan:
    """Separa o que o "Corrigir tudo" aplica do que deixa pendente.

    Só considera sinalizações **sem decisão** dentro do escopo. A ordem das
    unidades segue a ordem dos documentos e das páginas no relatório.

    Args:
        report: relatório no formato de ``analysis.schema.json``.
        scope_kind: ``batch`` ou ``document``.
        scope_id: identificador do lote ou do documento.
    """
    documents = [d for d in report["documents"] if scope_kind == "batch" or d["id"] == scope_id]
    page_doc = {pid: d for d in documents for pid in d["page_ids"]}
    doc_ids = {d["id"] for d in documents}
    by_target: dict[str, list[Mapping[str, Any]]] = {}
    skipped: list[dict[str, Any]] = []
    for finding in report["findings"]:
        target = finding["target"]
        if finding.get("decision"):
            continue
        if target["kind"] == "page" and target["id"] not in page_doc:
            continue
        if target["kind"] == "document" and target["id"] not in doc_ids:
            continue
        if target["kind"] == "batch" and scope_kind != "batch":
            continue
        if is_automatic(finding):
            by_target.setdefault(target["id"], []).append(finding)
        else:
            skipped.append(skip_entry(finding, *skip_reason(finding)))

    units: list[BulkUnit] = []
    positions = {pid: i for d in documents for i, pid in enumerate(d["page_ids"])}
    for doc in documents:
        for page_id in doc["page_ids"]:
            found = by_target.get(page_id, [])
            if not found:
                continue
            images = tuple(
                f for f in found if CorrectionAction(f["correction"]["action"]) in IMAGE_ACTIONS
            )
            units.append(
                BulkUnit(
                    label=f"{doc['name']} · p. {positions[page_id] + 1}",
                    page_id=page_id,
                    findings=tuple(found),
                    image_findings=images,
                )
            )
        for finding in by_target.get(doc["id"], []):
            units.append(
                BulkUnit(
                    label=f"{doc['name']} · reordenação",
                    page_id=None,
                    findings=(finding,),
                    image_findings=(),
                )
            )
    return BulkPlan(units=tuple(units), skipped=tuple(skipped))
