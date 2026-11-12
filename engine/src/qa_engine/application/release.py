"""Liberação por processo (ADR-0018): relatório parcial e passada final sem perder decisões.

O conferente abre cada processo assim que ele fica pronto. Cada relatório novo (parcial
ou final) é mesclado com o que já está gravado: decisões tomadas são mantidas, inclusive
as de achados que a mediana do lote completo não repetiria; numeração digitada e ordem
manual são reaplicadas. Na passada final, achado novo num processo que já tinha
decisões marca o processo como "reavaliar", só com os achados novos.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from qa_engine.application.profile import Profile
from qa_engine.application.review import ManualOrder, recompute_summary, set_manual_numbering
from qa_engine.domain.model import Severity


def _targets(doc: Mapping[str, Any]) -> set[str]:
    return {doc["id"], *doc["page_ids"]}


def merge_release(
    previous: Mapping[str, Any] | None,
    new: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    *,
    final: bool,
    overrides: Mapping[str, str] | None = None,
    manual_orders: Mapping[str, ManualOrder] | None = None,
) -> dict[str, Any]:
    """Junta o relatório novo ao gravado.

    Args:
        previous: relatório gravado (com as decisões vigentes) ou ``None``.
        new: relatório recém-montado (``analysis.schema.json``), sem decisões.
        profile: perfil do lote.
        batch_root: pasta do lote (para reler o ``numbering.json`` na re-resolução).
        final: passada final do lote.
        overrides: numeração digitada pelo revisor, por página.
        manual_orders: ordem escolhida pelo revisor, por documento.
    """
    merged: dict[str, Any] = copy.deepcopy(dict(new))
    if previous is not None:
        before = {f["id"]: f for f in previous["findings"]}
        for finding in merged["findings"]:
            old = before.get(finding["id"])
            if old is not None and old.get("decision"):
                finding["decision"] = old["decision"]
        present = {f["id"] for f in merged["findings"]}
        targets = {t for d in merged["documents"] for t in _targets(d)}
        merged["findings"] += [
            f
            for f in previous["findings"]
            if f.get("decision") and f["id"] not in present and f["target"]["id"] in targets
        ]
        # Metadados confirmados pelo revisor continuam confirmados.
        for doc_id, fields in previous.get("metadata", {}).items():
            if doc_id in merged.get("metadata", {}) and any(f.get("confirmed") for f in fields):
                merged["metadata"][doc_id] = fields
        if final:
            _mark_reevaluate(previous, merged, before)
    known = {p["id"] for p in merged["pages"]}
    docs = {d["id"] for d in merged["documents"]}
    typed = {pid: v for pid, v in (overrides or {}).items() if pid in known}
    orders = {doc: o for doc, o in (manual_orders or {}).items() if doc in docs}
    if typed or orders:
        merged = set_manual_numbering(merged, profile, batch_root, typed, orders)
    rank = {s.value: s.rank for s in Severity}
    merged["findings"].sort(
        key=lambda f: (-rank[f["severity"]], f["rule"], f["target"]["kind"], f["target"]["id"])
    )
    merged["batch"]["summary"] = recompute_summary(merged, profile)
    return merged


def _mark_reevaluate(
    previous: Mapping[str, Any],
    merged: dict[str, Any],
    before: Mapping[str, Mapping[str, Any]],
) -> None:
    """Processo que já tinha decisões e ganhou achado novo volta como "reavaliar"."""
    reviewed = {
        d["id"]
        for d in previous["documents"]
        if any(f.get("decision") and f["target"]["id"] in _targets(d) for f in previous["findings"])
    }
    old_marks = {d["id"]: d.get("reevaluate", []) for d in previous["documents"]}
    for doc in merged["documents"]:
        if doc["id"] not in reviewed:
            continue
        targets = _targets(doc)
        fresh = [
            f["id"]
            for f in merged["findings"]
            if f["target"]["id"] in targets and f["id"] not in before
        ]
        marks = sorted({*old_marks.get(doc["id"], []), *fresh})
        if marks:
            doc["reevaluate"] = marks


def queue_of(report: Mapping[str, Any], pending: Sequence[tuple[str, str]]) -> dict[str, Any]:
    """Fila da interface: processos prontos e os que faltam."""
    return {
        "ready": [{"id": d["id"], "name": d["name"]} for d in report["documents"]],
        "pending": [{"id": doc_id, "name": name} for doc_id, name in pending],
    }
