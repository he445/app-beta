"""Gestão: relatórios por caixa de todas as máquinas, por conferente, caixa e processo.

Lê os relatórios gravados na pasta compartilhada (``reports_dir``) — ou, sem ela, os
deste computador — e soma por período (``docs/especificacoes/gestao.md``). Não mede
tempo por caixa nem ordena conferentes: isso mudaria a ferramenta de apoio para
instrumento de cobrança individual, e só entra por decisão registrada em ADR.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any


def _when(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def version_key(version: str) -> tuple[int, ...] | None:
    """``1.2.10`` → ``(1, 2, 10)``; versão fora do padrão SemVer não é comparada."""
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version.strip())
    return tuple(int(part) for part in match.groups()) if match else None


def management_view(
    reports: Sequence[tuple[str, Mapping[str, Any]]],
    since: str | None = None,
    until: str | None = None,
    skipped: int = 0,
    shared: bool = False,
    seen: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Visão da Gestão (``management.schema.json``).

    Args:
        reports: pares (referência do relatório, relatório por caixa).
        since: início do período (inclusive), ISO 8601.
        until: fim do período (exclusive), ISO 8601.
        skipped: arquivos que não puderam ser lidos.
        shared: os relatórios vieram da pasta compartilhada.
        seen: versão e última abertura de cada máquina (``maquinas/`` da pasta
            compartilhada, ou só este computador).

    Uma caixa entra no período em que foi concluída (a primeira versão); o estado
    mostrado é o da versão mais nova até o fim do período.
    """
    start = _when(since) if since else None
    end = _when(until) if until else None
    versions: dict[tuple[str, str], list[tuple[str, Mapping[str, Any]]]] = {}
    machines: dict[str, dict[str, Any]] = {}
    for ref, report in reports:
        versions.setdefault((report["batch_id"], report["box"]), []).append((ref, report))
        machine = machines.setdefault(
            report["machine"],
            {"machine": report["machine"], "program_version": "", "last_report_at": ""},
        )
        if report["concluded_at"] >= machine["last_report_at"]:
            machine["last_report_at"] = report["concluded_at"]
            machine["program_version"] = report["program_version"]

    for item in seen:
        machine = machines.setdefault(
            item["machine"],
            {"machine": item["machine"], "program_version": "", "last_report_at": ""},
        )
        machine["last_seen_at"] = item["last_seen_at"]
        # A abertura mais recente diz a versão instalada hoje, mesmo sem relatório novo.
        if item["last_seen_at"] >= machine["last_report_at"]:
            machine["program_version"] = item["program_version"]
    newest = max(
        (k for k in (version_key(m["program_version"]) for m in machines.values()) if k),
        default=None,
    )
    for machine in machines.values():
        key = version_key(machine["program_version"])
        machine["outdated"] = bool(newest and key and key < newest)

    by_reviewer: dict[str, list[dict[str, Any]]] = {}
    for items in versions.values():
        items.sort(key=lambda item: item[1]["version"])
        first = items[0][1]
        concluded = _when(first["concluded_at"])
        if (start and concluded < start) or (end and concluded >= end):
            continue
        upto = [item for item in items if end is None or _when(item[1]["concluded_at"]) < end]
        ref, latest = upto[-1]
        by_reviewer.setdefault(first["reviewer"], []).append(
            {
                "box": latest["box"],
                "batch_name": latest["batch_name"],
                "machine": latest["machine"],
                "version": latest["version"],
                "versions": len(items),
                "state": latest["state"],
                "concluded_at": first["concluded_at"],
                "updated_at": latest["concluded_at"],
                "ref": ref,
                "totals": dict(latest["totals"]),
                "processes": [
                    {
                        "number": p["number"],
                        "pages": p["pages"],
                        "clean": p["clean"],
                        "missing": p["missing"]["count"],
                        "illegible": p["illegible"]["count"],
                    }
                    for p in latest["processes"]
                ],
            }
        )

    reviewers = []
    for reviewer, boxes in sorted(by_reviewer.items()):
        boxes.sort(key=lambda b: b["concluded_at"])
        reviewers.append(
            {
                "reviewer": reviewer,
                "boxes": len(boxes),
                "pages": sum(b["totals"]["pages"] for b in boxes),
                "items": boxes,
            }
        )
    all_boxes = [b for r in reviewers for b in r["items"]]
    return {
        "period": {"since": since, "until": until},
        "totals": {
            "boxes": len(all_boxes),
            "boxes_pending": sum(1 for b in all_boxes if b["state"] == "pending"),
            "processes": sum(b["totals"]["processes"] for b in all_boxes),
            "pages": sum(b["totals"]["pages"] for b in all_boxes),
        },
        "reviewers": reviewers,
        "machines": sorted(machines.values(), key=lambda m: m["machine"]),
        "source": {"shared": shared, "reports": len(reports), "skipped": skipped},
    }
