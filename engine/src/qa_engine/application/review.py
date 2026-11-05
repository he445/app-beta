"""Casos de uso RecordDecision e correção de numeração, sobre o relatório em JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from qa_engine.adapters.numbering import SidecarNumberingReader
from qa_engine.application.analyze import summarize
from qa_engine.application.layout import read_manifest
from qa_engine.application.profile import Profile
from qa_engine.application.serialize import (
    decision_json,
    finding_json,
    numbering_json,
    summary_json,
)
from qa_engine.detectors import sequence
from qa_engine.detectors.base import Stats
from qa_engine.detectors.registry import manifest
from qa_engine.domain import ids
from qa_engine.domain.model import (
    ColorMode,
    Correction,
    CorrectionAction,
    CorrectionClass,
    Decision,
    DecisionAction,
    Document,
    Finding,
    Page,
    Region,
    Severity,
    Target,
    TargetKind,
)
from qa_engine.domain.sequencing import Mark, PageCandidates, Reading, parse_folio

SEQUENCE_RULES = {"missing_page", "out_of_order", "numbering_review", "completeness_unverifiable"}


def decision_from_json(data: Mapping[str, Any]) -> Decision:
    """Decisão a partir de ``decision.schema.json``."""
    return Decision(
        action=DecisionAction(data["action"]),
        decided_at=datetime.fromisoformat(str(data["decided_at"]).replace("Z", "+00:00")),
        reviewer=str(data["reviewer"]),
        note=data.get("note"),
    )


def finding_from_json(data: Mapping[str, Any]) -> Finding:
    """Sinalização a partir de ``finding.schema.json``."""
    region = data.get("region")
    corr = data["correction"]
    return Finding(
        id=data["id"],
        target=Target(TargetKind(data["target"]["kind"]), data["target"]["id"]),
        rule=data["rule"],
        rule_version=data["rule_version"],
        severity=Severity(data["severity"]),
        measure=float(data["measure"]),
        threshold=float(data["threshold"]),
        confidence=float(data["confidence"]),
        correction=Correction(
            CorrectionClass(corr["kind"]),
            CorrectionAction(corr["action"]),
            corr["description"],
            dict(corr.get("params", {})),
        ),
        message=data["message"],
        region=Region(**region) if region else None,
        decision=decision_from_json(data["decision"]) if data.get("decision") else None,
    )


def recompute_summary(report: Mapping[str, Any], profile: Profile) -> dict[str, Any]:
    """Recalcula estados, veredito e métricas do relatório a partir das sinalizações atuais."""
    documents = [
        Document(d["id"], d["batch_id"], d["name"], tuple(d["page_ids"]))
        for d in report["documents"]
    ]
    pages = [
        Page(
            p["id"],
            p["document_id"],
            p["index"],
            p["source_file"],
            p["page_in_file"],
            p["width_px"],
            p["height_px"],
            p["dpi"],
            ColorMode(p["color_mode"]) if p["color_mode"] else None,
            p["sha256"],
            p["loaded"],
        )
        for p in report["pages"]
    ]
    findings = [finding_from_json(f) for f in report["findings"]]
    stations = {p["id"]: p.get("station") or "não identificada" for p in report["pages"]}
    summary = summarize(
        batch_id=report["batch"]["id"],
        profile=profile,
        documents=documents,
        pages=pages,
        findings=findings,
        stations=stations,
        lossy_files=report["batch"]["summary"].get("lossy_files", []),
    )
    return summary_json(summary)


def decide(
    finding: Mapping[str, Any],
    action: DecisionAction,
    reviewer: str,
    now: datetime,
    note: str | None = None,
) -> dict[str, Any]:
    """Registra a decisão do revisor numa sinalização (JSON) e devolve a nova versão."""
    updated = dict(finding)
    updated["decision"] = decision_json(Decision(action, now, reviewer, note))
    return updated


def baselines_json(baselines: Mapping[str, Mapping[str, Stats]]) -> dict[str, Any]:
    """Linhas de base para gravar ao lado do lote (reanálise de cópias corrigidas)."""
    return {
        rule: {k: {"median": s.median, "sigma": s.sigma, "n": s.n} for k, s in stats.items()}
        for rule, stats in baselines.items()
    }


def baselines_from_json(data: Mapping[str, Any]) -> dict[str, dict[str, Stats]]:
    """Inverso de :func:`baselines_json`."""
    return {
        rule: {k: Stats(float(v["median"]), float(v["sigma"]), int(v["n"])) for k, v in s.items()}
        for rule, s in data.items()
    }


def renumber(
    report: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    overrides: Mapping[str, str],
) -> dict[str, Any]:
    """Ressolve a sequência dos documentos com a numeração digitada pelo revisor.

    A numeração digitada vira uma marca única de confiança 1. As sinalizações de
    sequência são regeneradas; decisões já tomadas são preservadas quando a
    sinalização regenerada tem o mesmo identificador.

    Raises:
        ValueError: se algum valor digitado não for uma folha válida.
    """
    for value in overrides.values():
        if parse_folio(value) is None:
            raise ValueError(f"numeração inválida: {value!r}")
    new = json.loads(json.dumps(report))
    pages = {p["id"]: p for p in new["pages"]}
    keys = {f"{p['source_file']}#{p['page_in_file']}": p["id"] for p in new["pages"]}
    marks = SidecarNumberingReader().read(batch_root, list(keys))
    by_page: dict[str, Sequence[Mark]] = {keys[k]: v for k, v in marks.items()}
    for page_id, value in overrides.items():
        by_page[page_id] = (Mark((Reading(value, 1.0),)),)
    duplicates = {
        f["target"]["id"]: f["correction"]["params"].get("duplicate_of", "")
        for f in new["findings"]
        if f["rule"] == "duplicate_page"
    }
    declared = read_manifest(batch_root)
    previous = {f["id"]: f for f in new["findings"]}
    kept = [f for f in new["findings"] if f["rule"] not in SEQUENCE_RULES]
    regenerated: list[dict[str, Any]] = []
    counter: dict[tuple[str, str], int] = {}
    for doc in new["documents"]:
        cands = [PageCandidates(pid, tuple(by_page.get(pid, ()))) for pid in doc["page_ids"]]
        result, flags = sequence.analyze_document(
            doc["id"], cands, profile.sequence, declared.get(doc["name"]), duplicates
        )
        doc["proposed_order"] = list(result.order) if result.reordered else []
        for numbering in result.pages:
            pages[numbering.page_id]["numbering"] = numbering_json(numbering)
        for item in flags:
            if not profile.enabled(item.rule):
                continue
            key = (item.target.id, item.rule)
            ordinal = counter.get(key, 0)
            counter[key] = ordinal + 1
            finding = Finding(
                id=ids.finding_id(new["batch"]["id"], item.target.id, item.rule, ordinal),
                target=item.target,
                rule=item.rule,
                rule_version=manifest(item.rule).version,
                severity=profile.severity_override(item.rule) or item.flag.severity,
                measure=item.flag.measure,
                threshold=item.flag.threshold,
                confidence=round(item.flag.confidence, 4),
                correction=item.flag.correction,
                message=item.flag.message,
            )
            data = finding_json(finding)
            old = previous.get(finding.id)
            if old is not None and old.get("decision"):
                data["decision"] = old["decision"]
            regenerated.append(data)
    rank = {s.value: s.rank for s in Severity}
    new["findings"] = sorted(
        kept + regenerated,
        key=lambda f: (-rank[f["severity"]], f["rule"], f["target"]["kind"], f["target"]["id"]),
    )
    new["batch"]["summary"] = recompute_summary(new, profile)
    return dict(new)
