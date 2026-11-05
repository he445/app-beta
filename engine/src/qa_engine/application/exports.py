"""Caso de uso ExportReport: relatório, CSVs, metadados e ordem de retrabalho."""

from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from qa_engine.domain.model import (
    CorrectionClass,
    DecisionAction,
    Finding,
    TargetKind,
)


def findings_csv(
    findings: Iterable[Mapping[str, Any]], pages: Mapping[str, Mapping[str, Any]]
) -> str:
    """CSV de sinalizações, uma por linha, com arquivo e posição da página."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(
        [
            "finding_id",
            "severity",
            "rule",
            "target_kind",
            "target_id",
            "source_file",
            "page_in_file",
            "measure",
            "threshold",
            "confidence",
            "correction_kind",
            "correction_action",
            "decision",
            "message",
        ]
    )
    for f in findings:
        page = pages.get(f["target"]["id"], {})
        writer.writerow(
            [
                f["id"],
                f["severity"],
                f["rule"],
                f["target"]["kind"],
                f["target"]["id"],
                page.get("source_file", ""),
                page.get("page_in_file", ""),
                f["measure"],
                f["threshold"],
                f["confidence"],
                f["correction"]["kind"],
                f["correction"]["action"],
                (f.get("decision") or {}).get("action", ""),
                f["message"],
            ]
        )
    return out.getvalue()


def metadata_csv(report: Mapping[str, Any]) -> str:
    """CSV de metadados do lote: um documento por linha, uma coluna por metadado."""
    docs = {d["id"]: d["name"] for d in report["documents"]}
    rows: list[dict[str, Any]] = []
    columns: list[str] = ["document_id", "document"]
    for doc_id, fields in report["metadata"].items():
        row: dict[str, Any] = {"document_id": doc_id, "document": docs.get(doc_id, "")}
        for field in fields:
            value = field["value"]
            row[field["name"]] = json.dumps(value) if isinstance(value, dict) else value
            if field["name"] not in columns:
                columns.append(field["name"])
        rows.append(row)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def rework_items(report: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Ordem de retrabalho: ações físicas não descartadas pelo revisor, por estação e caixa.

    Entra toda sinalização de classe ``physical`` sem decisão ou reprovada, e
    toda sinalização reprovada (R) de qualquer classe.
    """
    pages = {p["id"]: p for p in report["pages"]}
    docs = {d["id"]: d for d in report["documents"]}
    items: list[dict[str, Any]] = []
    for f in report["findings"]:
        decision = (f.get("decision") or {}).get("action")
        physical = f["correction"]["kind"] == CorrectionClass.PHYSICAL.value
        rejected = decision == DecisionAction.REJECT.value
        if not (rejected or (physical and decision is None)):
            continue
        if f["target"]["kind"] == TargetKind.PAGE.value:
            page = pages[f["target"]["id"]]
            doc = docs[page["document_id"]]
            position: Any = page["index"] + 1
            station = page.get("station") or "não identificada"
            source = page["source_file"]
        else:
            doc = docs.get(f["target"]["id"], {"name": "", "page_ids": []})
            first = pages.get(doc["page_ids"][0], {}) if doc["page_ids"] else {}
            position = ""
            station = first.get("station") or "não identificada"
            source = first.get("source_file", "")
        parts = doc["name"].split("/")
        items.append(
            {
                "station": station,
                "box": parts[0] if len(parts) > 1 else "",
                "document": doc["name"],
                "page_position": position,
                "source_file": source,
                "rule": f["rule"],
                "severity": f["severity"],
                "action": f["correction"]["action"],
                "instruction": f["correction"]["description"],
                "settings": json.dumps(f["correction"].get("params", {}), ensure_ascii=False),
                "finding_id": f["id"],
            }
        )
    items.sort(key=lambda i: (i["station"], i["box"], i["document"], str(i["page_position"])))
    return items


def rework_csv(report: Mapping[str, Any]) -> str:
    """Ordem de retrabalho em CSV, para o setor de digitalização."""
    items = rework_items(report)
    out = io.StringIO()
    fields = [
        "station",
        "box",
        "document",
        "page_position",
        "source_file",
        "rule",
        "severity",
        "action",
        "instruction",
        "settings",
        "finding_id",
    ]
    writer = csv.DictWriter(out, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(items)
    return out.getvalue()


def write_exports(report: Mapping[str, Any], out_dir: Path) -> list[Path]:
    """Grava relatório, CSVs e um JSON de metadados por documento em ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pages = {p["id"]: p for p in report["pages"]}
    written = {
        "report.json": json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False),
        "findings.csv": findings_csv(report["findings"], pages),
        "metadata.csv": metadata_csv(report),
        "rework_order.csv": rework_csv(report),
    }
    paths: list[Path] = []
    for name, text in written.items():
        path = out_dir / name
        path.write_text(text + ("" if text.endswith("\n") else "\n"), encoding="utf-8")
        paths.append(path)
    meta_dir = out_dir / "metadata"
    meta_dir.mkdir(exist_ok=True)
    for doc in report["documents"]:
        path = meta_dir / f"{doc['name'].replace('/', '__')}.json"
        path.write_text(
            json.dumps(
                {
                    "document_id": doc["id"],
                    "document": doc["name"],
                    "fields": report["metadata"][doc["id"]],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        paths.append(path)
    return paths


def pending_findings(findings: Iterable[Finding]) -> list[Finding]:
    """Sinalizações ainda pendentes."""
    return [f for f in findings if f.pending]
