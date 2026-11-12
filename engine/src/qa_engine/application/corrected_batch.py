"""Plano e manifesto do lote corrigido (``docs/especificacoes/corrections.md``).

Funções puras sobre o relatório: a mesma lógica alimenta a faixa "Depois" da
interface (``GET /batches/{id}/corrected-plan``) e o ``manifest.json`` do zip.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping, Sequence
from pathlib import PurePosixPath
from typing import Any

from qa_engine.application.bulk import RESCAN_RULES
from qa_engine.application.complements import is_complement
from qa_engine.application.corrections import CANONICAL_ORDER, describe_correction
from qa_engine.application.review import finding_from_json
from qa_engine.domain.model import CorrectionAction, CorrectionClass, DecisionAction

PDF_RASTER_DPI = 300.0
"""PDF é rasterizado a 300 dpi para correção e exportação."""

REMOVAL_REASON = {"blank_page": "em branco", "duplicate_page": "duplicada"}
NOT_LOADED_REASON = "arquivo ilegível: precisa redigitalizar"


def raster_dpi(page: Mapping[str, Any]) -> float | None:
    """Resolução da imagem que o motor carrega para a página."""
    if str(page["source_file"]).lower().endswith(".pdf"):
        return PDF_RASTER_DPI
    dpi = page.get("dpi")
    return float(dpi) if dpi else None


def document_folder(document: Mapping[str, Any], pages: Mapping[str, Mapping[str, Any]]) -> str:
    """Pasta do documento no lote corrigido, espelhando a estrutura original.

    Documento de imagens soltas numa pasta → a mesma pasta (raiz = vazio).
    Documento que veio de um arquivo multipágina (PDF, TIFF) → pasta com o nome
    do arquivo, sem extensão.
    """
    originals = [
        pid for pid in document["page_ids"] if not is_complement(pages[pid]["source_file"])
    ]
    first = pages[originals[0]] if originals else None
    if first is None:
        return str(document["name"])
    source = str(first["source_file"])
    multipage = source.lower().endswith(".pdf") or any(
        pages[pid]["page_in_file"] > 0 for pid in originals
    )
    if multipage:
        return source.rsplit(".", 1)[0]
    parent = PurePosixPath(source).parent.as_posix()
    return "" if parent == "." else parent


def _decided(finding: Mapping[str, Any], action: DecisionAction) -> bool:
    decision = finding.get("decision")
    return bool(decision and decision["action"] == action.value)


def _change(finding: Mapping[str, Any], text: str) -> dict[str, Any]:
    decision = finding.get("decision") or {}
    return {
        "finding_id": finding["id"],
        "rule": finding["rule"],
        "action": finding["correction"]["action"],
        "text": text,
        "params": dict(finding["correction"].get("params", {})),
        "decided_by": decision.get("reviewer"),
        "decided_at": decision.get("decided_at"),
    }


def _is_pending(finding: Mapping[str, Any]) -> bool:
    return finding_from_json(finding).pending


def build_plan(
    report: Mapping[str, Any], operations: Sequence[Mapping[str, Any]] = ()
) -> dict[str, Any]:
    """Como o lote corrigido fica com as decisões atuais.

    Regras: a ordem final é ``manual_order`` (escolhida pelo revisor) quando houver;
    senão ``proposed_order`` quando a reordenação foi aceita (``correct``), senão a
    original; páginas com remoção aceita ficam fora;
    páginas ilegíveis não são exportadas; os arquivos são renumerados em
    sequência por documento.

    Args:
        report: relatório no formato de ``analysis.schema.json``.
        operations: operações de correção em lote do lote.

    Returns:
        Documento no formato de ``corrected-plan.schema.json``.
    """
    pages = {p["id"]: p for p in report["pages"]}
    by_target: dict[str, list[Mapping[str, Any]]] = {}
    for finding in report["findings"]:
        by_target.setdefault(finding["target"]["id"], []).append(finding)

    documents: list[dict[str, Any]] = []
    blockers: list[dict[str, Any]] = []
    for doc in report["documents"]:
        doc_findings = by_target.get(doc["id"], [])
        reorder = next(
            (f for f in doc_findings if f["correction"]["action"] == CorrectionAction.REORDER),
            None,
        )
        reordered = bool(
            reorder and _decided(reorder, DecisionAction.CORRECT) and doc["proposed_order"]
        )
        manual = doc.get("manual_order")
        if manual:
            order = list(manual["page_ids"])
        else:
            order = list(doc["proposed_order"]) if reordered else list(doc["page_ids"])
        old_position = {pid: i + 1 for i, pid in enumerate(doc["page_ids"])}
        folder = document_folder(doc, pages)

        items: dict[str, dict[str, Any]] = {}
        for pid in doc["page_ids"]:
            page = pages[pid]
            found = by_target.get(pid, [])
            removal = next(
                (
                    f
                    for f in found
                    if f["correction"]["action"] == CorrectionAction.REMOVE_PAGE
                    and _decided(f, DecisionAction.CORRECT)
                ),
                None,
            )
            images = sorted(
                (
                    f
                    for f in found
                    if f["correction"]["kind"] == CorrectionClass.AUTOMATIC.value
                    and CorrectionAction(f["correction"]["action"]) in CANONICAL_ORDER
                    and _decided(f, DecisionAction.CORRECT)
                ),
                key=lambda f: (
                    CANONICAL_ORDER.index(CorrectionAction(f["correction"]["action"])),
                    f["id"],
                ),
            )
            rescan = [
                {"finding_id": f["id"], "rule": f["rule"], "text": f["message"]}
                for f in found
                if _is_pending(f)
                and (
                    f["rule"] in RESCAN_RULES
                    or f["correction"]["kind"] == CorrectionClass.PHYSICAL.value
                )
            ]
            status, reason = "exported", None
            if not page["loaded"]:
                status, reason = "not_exported", NOT_LOADED_REASON
            elif removal is not None:
                status = "removed"
                reason = REMOVAL_REASON.get(removal["rule"], removal["message"])
            items[pid] = {
                "page_id": pid,
                "source_file": page["source_file"],
                "source_page": page["page_in_file"],
                "source_sha256": page["sha256"],
                "old_position": old_position[pid],
                "new_position": None,
                "target_file": None,
                "dpi": raster_dpi(page),
                "status": status,
                "reason": reason,
                "corrected": bool(images) and status == "exported",
                "moved": False,
                "changes": [
                    _change(
                        f, describe_correction(f["correction"]["action"], f["correction"]["params"])
                    )
                    for f in images
                ],
                "needs_rescan": rescan,
            }
            if removal is not None:
                items[pid]["changes"].append(_change(removal, f"removida: {reason}"))

        kept = [pid for pid in order if items[pid]["status"] == "exported"]
        original_rank = {
            pid: i
            for i, pid in enumerate(p for p in doc["page_ids"] if items[p]["status"] == "exported")
        }
        for new_index, pid in enumerate(kept):
            item = items[pid]
            item["new_position"] = new_index + 1
            name = f"{new_index + 1:04d}.tif"
            item["target_file"] = f"{folder}/{name}" if folder else name
            if manual and original_rank[pid] != new_index:
                item["moved"] = True
                item["changes"].append(
                    {
                        "finding_id": None,
                        "rule": "out_of_order",
                        "action": CorrectionAction.REORDER.value,
                        "text": f"movida da posição {item['old_position']} para a "
                        f"{new_index + 1} pelo revisor",
                        "params": {},
                        "decided_by": manual["reviewer"],
                        "decided_at": manual["decided_at"],
                    }
                )
            elif reordered and reorder is not None and original_rank[pid] != new_index:
                item["moved"] = True
                item["changes"].append(
                    _change(
                        reorder,
                        f"movida da posição {item['old_position']} para a {new_index + 1}",
                    )
                )

        missing: list[dict[str, Any]] = []
        for finding in doc_findings:
            if finding["rule"] != "missing_page":
                continue
            params = finding["correction"].get("params", {})
            after = params.get("after_page_id")
            entry = {
                "finding_id": finding["id"],
                "missing": [str(m) for m in params.get("missing", [])],
                "after_page_id": after,
                "before_page_id": params.get("before_page_id"),
                "after_position": old_position.get(after) if after else None,
                "message": finding["message"],
                "decision": finding.get("decision"),
            }
            missing.append(entry)
            if not finding.get("decision"):
                blockers.append(
                    {
                        "finding_id": finding["id"],
                        "document_id": doc["id"],
                        "document": doc["name"],
                        "message": f"{doc['name']}: {finding['message']} Decida antes de salvar.",
                    }
                )

        documents.append(
            {
                "document_id": doc["id"],
                "name": doc["name"],
                "folder": folder,
                "reordered": reordered or bool(manual),
                "pages": [items[pid] for pid in doc["page_ids"]],
                "missing": missing,
            }
        )

    pending = [f for f in report["findings"] if _is_pending(f)]
    return {
        "batch_id": report["batch"]["id"],
        "can_save": not blockers,
        "blockers": blockers,
        "pending_critical": sum(f["severity"] == "critical" for f in pending),
        "pending_rescan": sum(
            f["rule"] in RESCAN_RULES or f["correction"]["kind"] == CorrectionClass.PHYSICAL.value
            for f in pending
            if f["rule"] != "missing_page"
        ),
        "unsaved_operations": [op["id"] for op in operations if op["status"] == "applied"],
        "documents": documents,
    }


def plan_totals(documents: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Totais do manifesto."""
    pages = [p for d in documents for p in d["pages"]]
    return {
        "exported": sum(p["status"] == "exported" for p in pages),
        "removed": sum(p["status"] == "removed" for p in pages),
        "not_exported": sum(p["status"] == "not_exported" for p in pages),
        "corrected": sum(p["corrected"] for p in pages),
        "moved": sum(p["moved"] for p in pages),
        "missing_pages": sum(len(d["missing"]) for d in documents),
    }


def manifest_csv(manifest: Mapping[str, Any]) -> str:
    """``manifest.csv``: uma linha por página de origem e uma por página faltando."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        [
            "document",
            "status",
            "source_file",
            "source_page",
            "old_position",
            "new_position",
            "target_file",
            "changes",
            "reason",
            "needs_rescan",
            "decision",
            "source_sha256",
            "target_sha256",
        ]
    )
    for doc in manifest["documents"]:
        for page in doc["pages"]:
            writer.writerow(
                [
                    doc["name"],
                    page["status"],
                    page["source_file"],
                    page["source_page"],
                    page["old_position"],
                    page["new_position"] or "",
                    page["target_file"] or "",
                    "; ".join(c["text"] for c in page["changes"]),
                    page["reason"] or "",
                    "; ".join(r["text"] for r in page["needs_rescan"]),
                    "",
                    page["source_sha256"],
                    page.get("target_sha256", ""),
                ]
            )
        for gap in doc["missing"]:
            decision = gap["decision"]
            writer.writerow(
                [
                    doc["name"],
                    "missing",
                    "",
                    "",
                    gap["after_position"] or "",
                    "",
                    "",
                    "",
                    gap["message"],
                    "",
                    f"{decision['action']} por {decision['reviewer']} em {decision['decided_at']}"
                    if decision
                    else "",
                    "",
                    "",
                ]
            )
    return out.getvalue()
