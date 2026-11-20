"""Relatório por caixa: o que falta, o que está ilegível e os defeitos de imagem de cada processo.

Substitui a folha de papel das pendências (``docs/especificacoes/relatorio-por-caixa.md``).
A caixa é a primeira pasta do lote e o processo é o documento. O relatório sai quando
todas as decisões da caixa foram tomadas; se uma pendência muda depois, sai uma versão
nova e a anterior fica guardada.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

ILLEGIBLE_RULES = frozenset({"corrupted_file"})
"""Página ilegível de fato: o arquivo não abre ou não se lê."""
TYPED_DEFECTS: dict[str, str] = {
    "blur": "Páginas desfocadas",
    "exposure": "Páginas com exposição ruim (clara ou escura demais)",
    "low_resolution": "Páginas com resolução abaixo do exigido",
}
"""Defeitos de imagem tipificados no relatório: a página existe e se lê, mas tem o defeito.

Antes (ADR-0030) entravam todos como "ilegível"; agora cada um sai com o seu tipo.
"""
LEGIBILITY_RULES = ILLEGIBLE_RULES | frozenset(TYPED_DEFECTS)
"""Regras de imagem que entram no relatório quando confirmadas."""
CONFIRMED = frozenset({"reject", "source_defect"})
"""Decisões que confirmam a pendência (retrabalho ou defeito de origem)."""
SCHEMA_VERSION = "1"


def box_of(document_name: str, batch_name: str) -> str:
    """A caixa de um documento: a primeira pasta do lote (ou o próprio lote, sem pastas)."""
    parts = [p for p in document_name.replace("\\", "/").split("/") if p]
    return parts[0] if len(parts) > 1 else batch_name


def process_number(document_name: str) -> str:
    """O número do processo: a última pasta do documento."""
    parts = [p for p in document_name.replace("\\", "/").split("/") if p]
    return parts[-1] if parts else document_name


def boxes(report: Mapping[str, Any]) -> dict[str, list[Mapping[str, Any]]]:
    """Documentos de cada caixa, na ordem do lote."""
    out: dict[str, list[Mapping[str, Any]]] = {}
    for doc in report["documents"]:
        out.setdefault(box_of(doc["name"], report["batch"]["name"]), []).append(doc)
    return out


def _targets(docs: Sequence[Mapping[str, Any]]) -> set[str]:
    return {d["id"] for d in docs} | {pid for d in docs for pid in d["page_ids"]}


BLOCKING_SEVERITIES = frozenset({"medium", "high", "critical"})
"""Severidades que exigem decisão para concluir a caixa.

Sinalização baixa é tratada em massa e não exige revisão (``pages_needing_review``);
o documento só com baixas pendentes já é verde. Nenhuma regra que entra no relatório
(folha faltando, legibilidade) sai como baixa.
"""


def pending_findings(
    report: Mapping[str, Any], docs: Sequence[Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    """Sinalizações da caixa que ainda impedem a conclusão: médio ou acima, sem decisão."""
    targets = _targets(docs)
    return [
        f
        for f in report["findings"]
        if f["target"]["id"] in targets
        and f["severity"] in BLOCKING_SEVERITIES
        and not f.get("decision")
    ]


def is_complete(report: Mapping[str, Any], docs: Sequence[Mapping[str, Any]]) -> bool:
    """A caixa está concluída: toda sinalização médio ou acima tem decisão (retrabalho conta)."""
    return not pending_findings(report, docs)


def folios_text(folios: Sequence[str]) -> str:
    """``fls. 13, 14 e 15``."""
    if not folios:
        return ""
    if len(folios) == 1:
        return f"fls. {folios[0]}"
    return f"fls. {', '.join(folios[:-1])} e {folios[-1]}"


def _page_folio(page: Mapping[str, Any]) -> str | None:
    numbering = page.get("numbering") or {}
    if "typed" in numbering:
        return str(numbering["typed"])
    if numbering.get("state") in {"read", "renumbered"} and numbering.get("value"):
        return str(numbering["value"])
    return None


def process_entry(report: Mapping[str, Any], doc: Mapping[str, Any]) -> dict[str, Any]:
    """Pendências de um processo: folhas faltando e páginas ilegíveis confirmadas."""
    pages = {p["id"]: p for p in report["pages"]}
    order = (doc.get("manual_order") or {}).get("page_ids") or doc["page_ids"]
    position = {pid: i + 1 for i, pid in enumerate(order)}
    missing: list[str] = []
    missing_count = 0
    illegible: dict[str, dict[str, Any]] = {}
    typed: dict[str, dict[str, dict[str, Any]]] = {rule: {} for rule in TYPED_DEFECTS}
    for finding in report["findings"]:
        action = (finding.get("decision") or {}).get("action")
        if action not in CONFIRMED:
            continue
        target = finding["target"]["id"]
        if finding["rule"] == "missing_page" and target == doc["id"]:
            folios = [str(m) for m in finding["correction"].get("params", {}).get("missing", [])]
            missing += folios
            missing_count += len(folios) or 1
        elif finding["rule"] in LEGIBILITY_RULES and target in position:
            bucket = illegible if finding["rule"] in ILLEGIBLE_RULES else typed[finding["rule"]]
            if target not in bucket:
                bucket[target] = _page_entry(pages[target], position[target])
    listed = sorted(illegible.values(), key=lambda item: item["position"])
    defects = [
        {
            "rule": rule,
            "label": TYPED_DEFECTS[rule],
            "count": len(found),
            "pages": sorted(found.values(), key=lambda item: item["position"]),
        }
        for rule, found in typed.items()
        if found
    ]
    return {
        "document_id": doc["id"],
        "number": process_number(doc["name"]),
        "pages": len(doc["page_ids"]),
        "missing": {"count": missing_count, "folios": missing},
        "illegible": {"count": len(listed), "pages": listed},
        "defects": defects,
        "clean": missing_count == 0 and not listed and not defects,
    }


def _page_entry(page: Mapping[str, Any], position: int) -> dict[str, Any]:
    return {
        "folio": _page_folio(page),
        "position": position,
        "file": str(page["source_file"]).replace("\\", "/").split("/")[-1],
    }


def build_box_report(
    report: Mapping[str, Any],
    box: str,
    docs: Sequence[Mapping[str, Any]],
    *,
    reviewer: str,
    concluded_at: str,
    machine: str,
    program_version: str,
    version: int,
    previous_pending: bool = False,
) -> dict[str, Any]:
    """O relatório de uma caixa (``box-report.schema.json``)."""
    processes = [process_entry(report, doc) for doc in docs]
    pending = any(not p["clean"] for p in processes)
    state = "pending" if pending else ("resolved" if previous_pending else "clean")
    return {
        "schema_version": SCHEMA_VERSION,
        "box": box,
        "batch_id": report["batch"]["id"],
        "batch_name": report["batch"]["name"],
        "version": version,
        "state": state,
        "reviewer": reviewer,
        "concluded_at": concluded_at,
        "machine": machine,
        "program_version": program_version,
        "processes": processes,
        "totals": {
            "processes": len(processes),
            "pages": sum(p["pages"] for p in processes),
            "missing": sum(p["missing"]["count"] for p in processes),
            "illegible": sum(p["illegible"]["count"] for p in processes),
            "defects": sum(d["count"] for p in processes for d in p.get("defects", [])),
        },
    }


def pendencies_key(box_report: Mapping[str, Any]) -> str:
    """O que muda o relatório: as pendências de cada processo (não a data nem o conferente)."""
    return json.dumps(
        [
            [p["number"], p["missing"], p["illegible"], p["pages"], p.get("defects", [])]
            for p in box_report["processes"]
        ],
        sort_keys=True,
        ensure_ascii=False,
    )


def process_lines(process: Mapping[str, Any]) -> list[str]:
    """As linhas de um processo, como saem no PDF."""
    if process["clean"]:
        return ["Nenhuma pendência"]
    lines = []
    missing = process["missing"]
    if missing["count"]:
        folios = folios_text(missing["folios"])
        lines.append(f"Páginas faltando: {missing['count']}" + (f" — {folios}" if folios else ""))
    illegible = process["illegible"]
    if illegible["count"]:
        lines.append(f"Páginas ilegíveis: {illegible['count']} — {_where(illegible['pages'])}")
    for defect in process.get("defects", []):
        lines.append(f"{defect['label']}: {defect['count']} — {_where(defect['pages'])}")
    return lines


def _where(pages: Sequence[Mapping[str, Any]]) -> str:
    """``fls. 7, posição 3 (p0003.tif)``: o número da folha, senão a posição e o arquivo."""
    return ", ".join(
        f"fls. {p['folio']}" if p["folio"] else f"posição {p['position']} ({p['file']})"
        for p in pages
    )
