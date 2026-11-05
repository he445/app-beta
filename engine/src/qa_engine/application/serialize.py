"""Conversão das entidades para o JSON do contrato (``contracts/schemas``)."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any

from qa_engine.application.analyze import BatchAnalysis, BatchSummary
from qa_engine.application.metadata import MetadataField
from qa_engine.domain.model import Decision, Finding, Page
from qa_engine.domain.sequencing import PageNumbering


def iso(dt: datetime) -> str:
    """ISO 8601 em UTC, com sufixo ``Z``."""
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def decision_json(decision: Decision) -> dict[str, Any]:
    """Decisão no formato de ``decision.schema.json``."""
    data: dict[str, Any] = {
        "action": decision.action.value,
        "decided_at": iso(decision.decided_at),
        "reviewer": decision.reviewer,
    }
    if decision.note:
        data["note"] = decision.note
    return data


def finding_json(finding: Finding) -> dict[str, Any]:
    """Sinalização no formato de ``finding.schema.json``."""
    data: dict[str, Any] = {
        "id": finding.id,
        "target": {"kind": finding.target.kind.value, "id": finding.target.id},
        "rule": finding.rule,
        "rule_version": finding.rule_version,
        "severity": finding.severity.value,
        "measure": finding.measure,
        "threshold": finding.threshold,
        "confidence": finding.confidence,
        "message": finding.message,
        "correction": {
            "kind": finding.correction.kind.value,
            "action": finding.correction.action.value,
            "description": finding.correction.description,
            "params": dict(finding.correction.params),
        },
    }
    if finding.region is not None:
        r = finding.region
        data["region"] = {"x": r.x, "y": r.y, "w": r.w, "h": r.h}
    if finding.decision is not None:
        data["decision"] = decision_json(finding.decision)
    return data


def numbering_json(numbering: PageNumbering) -> dict[str, Any]:
    """Numeração resolvida de uma página."""
    return {
        "state": numbering.state.value,
        "value": str(numbering.value) if numbering.value is not None else None,
        "confidence": round(numbering.confidence, 4),
        "previous": list(numbering.previous),
    }


def page_json(page: Page, numbering: PageNumbering | None, station: str | None) -> dict[str, Any]:
    """Página no formato de ``page.schema.json``."""
    data: dict[str, Any] = {
        "id": page.id,
        "document_id": page.document_id,
        "index": page.index,
        "source_file": page.source_file,
        "page_in_file": page.page_in_file,
        "width_px": page.width_px,
        "height_px": page.height_px,
        "dpi": page.dpi,
        "color_mode": page.color_mode.value if page.color_mode else None,
        "sha256": page.sha256,
        "loaded": page.loaded,
        "station": station,
    }
    if numbering is not None:
        data["numbering"] = numbering_json(numbering)
    return data


def metadata_json(field: MetadataField) -> dict[str, Any]:
    """Metadado no formato de ``metadata-field.schema.json``."""
    data: dict[str, Any] = {
        "name": field.name,
        "value": field.value,
        "source": field.source.value,
        "confidence": field.confidence,
        "required_by_decree": field.required_by_decree,
        "confirmed": field.confirmed,
    }
    if field.note:
        data["note"] = field.note
    return data


def summary_json(summary: BatchSummary) -> dict[str, Any]:
    """Painel do lote."""
    return {
        "verdict": summary.verdict.value,
        "pages_total": summary.pages_total,
        "pages_without_review": summary.pages_without_review,
        "no_review_ratio": round(summary.no_review_ratio, 4),
        "documents_total": summary.documents_total,
        "document_states": {k: v.value for k, v in summary.document_states.items()},
        "by_severity": dict(summary.by_severity),
        "by_rule": dict(summary.by_rule),
        "by_station": dict(summary.by_station),
        "green_sample": list(summary.green_sample),
        "review_pages": list(summary.review_pages),
        "lossy_files": list(summary.lossy_files),
    }


def analysis_json(
    analysis: BatchAnalysis, findings: Mapping[str, Finding] | None = None
) -> dict[str, Any]:
    """Resultado completo no formato de ``analysis.schema.json``."""
    current = list(findings.values()) if findings is not None else list(analysis.findings)
    return {
        "batch": {
            "id": analysis.batch_id,
            "name": analysis.name,
            "profile_id": analysis.profile_id,
            "analyzed_at": iso(analysis.analyzed_at),
            "engine_version": analysis.engine_version,
            "summary": summary_json(analysis.summary),
        },
        "documents": [
            {
                "id": d.id,
                "batch_id": d.batch_id,
                "name": d.name,
                "page_ids": list(d.page_ids),
                "state": analysis.summary.document_states[d.id].value,
                "proposed_order": list(analysis.proposed_order.get(d.id, ())),
            }
            for d in analysis.documents
        ],
        "pages": [
            page_json(p, analysis.numbering.get(p.id), analysis.stations.get(p.id))
            for p in analysis.pages
        ],
        "findings": [finding_json(f) for f in current],
        "metadata": {
            doc_id: [metadata_json(f) for f in fields]
            for doc_id, fields in analysis.metadata.items()
        },
    }
