"""Casos de uso RecordDecision e correção de numeração, sobre o relatório em JSON."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
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
        operation_id=data.get("operation_id"),
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
    operation_id: str | None = None,
) -> dict[str, Any]:
    """Registra a decisão do revisor numa sinalização (JSON) e devolve a nova versão.

    Args:
        finding: sinalização no formato do contrato.
        action: decisão tomada.
        reviewer: quem decidiu.
        now: quando decidiu (UTC).
        note: observação opcional.
        operation_id: operação de correção em lote, quando a decisão vem de "Corrigir tudo".
    """
    updated = dict(finding)
    updated["decision"] = decision_json(Decision(action, now, reviewer, note, operation_id))
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


def report_marks(
    pages: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, tuple[Mark, ...]], dict[str, str]]:
    """Marcas lidas na análise (``numbering.marks``) e a origem de cada uma, por página.

    Com o leitor por imagem, as marcas não estão em arquivo nenhum do lote: a
    re-resolução usa as que a análise gravou no relatório.
    """
    by_page: dict[str, tuple[Mark, ...]] = {}
    sources: dict[str, str] = {}
    for page in pages:
        numbering = page.get("numbering") or {}
        if "marks" not in numbering:
            continue
        by_page[page["id"]] = tuple(
            Mark(
                tuple(Reading(r["text"], float(r["confidence"])) for r in m["readings"]),
                bool(m.get("struck", False)),
            )
            for m in numbering["marks"]
        )
        sources[page["id"]] = str(numbering.get("source", "image"))  # image ou sidecar
    return by_page, sources


@dataclass(frozen=True, slots=True)
class ManualOrder:
    """Ordem das páginas de um documento escolhida pelo revisor."""

    page_ids: tuple[str, ...]
    reviewer: str
    decided_at: str


def set_manual_numbering(
    report: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    overrides: Mapping[str, str],
    manual_orders: Mapping[str, ManualOrder] | None = None,
) -> dict[str, Any]:
    """Caso de uso da tela de Sequência: numeração digitada e ordem escolhida pelo revisor.

    Valida tudo antes de mudar qualquer coisa e devolve o relatório com estado, ordem e
    lacunas de cada documento recalculados (:func:`renumber`).

    Raises:
        ValueError: valor que não é folha, página de outro documento ou ordem que não
            é uma permutação das páginas do documento.
    """
    documents = {d["id"]: d for d in report["documents"]}
    known = {pid for d in report["documents"] for pid in d["page_ids"]}
    for page_id in overrides:
        if page_id not in known:
            raise ValueError(f"página desconhecida: {page_id}")
    for doc_id, order in (manual_orders or {}).items():
        doc = documents.get(doc_id)
        if doc is None:
            raise ValueError(f"documento desconhecido: {doc_id}")
        if sorted(order.page_ids) != sorted(doc["page_ids"]):
            raise ValueError("a ordem precisa ter cada página do documento uma vez")
    return renumber(report, profile, batch_root, overrides, manual_orders)


def renumber(
    report: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    overrides: Mapping[str, str],
    manual_orders: Mapping[str, ManualOrder] | None = None,
) -> dict[str, Any]:
    """Ressolve a sequência dos documentos com a numeração digitada pelo revisor.

    A numeração digitada vira uma marca única de confiança 1. Com ordem escolhida pelo
    revisor, a sequência é resolvida nessa ordem e ela vai para o lote corrigido
    (``manual_order``). As sinalizações de sequência são regeneradas; decisões já
    tomadas são preservadas quando a sinalização regenerada tem o mesmo identificador.

    Raises:
        ValueError: se algum valor digitado não for uma folha válida.
    """
    for value in overrides.values():
        if parse_folio(value) is None:
            raise ValueError(f"numeração inválida: {value!r}")
    manual_orders = manual_orders or {}
    new = json.loads(json.dumps(report))
    pages = {p["id"]: p for p in new["pages"]}
    keys = {f"{p['source_file']}#{p['page_in_file']}": p["id"] for p in new["pages"]}
    read, sources = report_marks(new["pages"])
    if not read:
        marks = SidecarNumberingReader().read(batch_root, list(keys))
        read = {keys[k]: tuple(v) for k, v in marks.items()}
        sources = dict.fromkeys(read, "sidecar")
    by_page: dict[str, tuple[Mark, ...]] = dict(read)
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
        manual = manual_orders.get(doc["id"])
        if manual:
            doc["manual_order"] = {
                "page_ids": list(manual.page_ids),
                "reviewer": manual.reviewer,
                "decided_at": manual.decided_at,
            }
        else:
            doc.pop("manual_order", None)
        sequence_ids = list(manual.page_ids) if manual else list(doc["page_ids"])
        cands = [PageCandidates(pid, tuple(by_page.get(pid, ()))) for pid in sequence_ids]
        result, flags = sequence.analyze_document(
            doc["id"], cands, profile.sequence, declared.get(doc["name"]), duplicates
        )
        doc["proposed_order"] = list(result.order) if result.reordered else []
        for numbering in result.pages:
            pid = numbering.page_id
            pages[pid]["numbering"] = numbering_json(
                numbering,
                read.get(pid, ()),
                sources.get(pid),
                str(overrides[pid]) if pid in overrides else None,
            )
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
