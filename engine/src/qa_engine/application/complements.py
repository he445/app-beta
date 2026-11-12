"""Folha inserida depois (a faltante apareceu): área de complementos do lote.

A folha escaneada de novo é guardada na pasta de trabalho do lote, nunca na pasta
original, analisada como as outras e encaixada na posição escolhida ou sugerida pelo
número lido (``docs/especificacoes/folha-inserida.md``). Remover desfaz.
"""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any

from qa_engine.application.profile import Profile
from qa_engine.application.review import ManualOrder, recompute_summary, renumber
from qa_engine.domain.sequencing import Folio, Mark, parse_folio

COMPLEMENTS_DIR = "complementos"
"""Pasta, dentro da pasta de trabalho do lote, com as folhas inseridas."""
COMPLEMENT_PREFIX = ":complemento:/"
"""Prefixo do ``source_file`` de uma folha inserida. ``:`` não existe em nome de arquivo
no Windows, então nunca colide com um arquivo do lote original."""


def is_complement(source_file: str) -> bool:
    """A página é uma folha inserida depois."""
    return str(source_file).startswith(COMPLEMENT_PREFIX)


def complement_source(name: str) -> str:
    """``source_file`` de uma folha inserida guardada como ``name``."""
    return f"{COMPLEMENT_PREFIX}{name}"


def page_path(root: Path, work: Path | None, source_file: str) -> Path:
    """Arquivo de uma página: no lote original ou na área de complementos."""
    if is_complement(source_file):
        if work is None:
            raise FileNotFoundError("folha inserida sem pasta de trabalho")
        name = PurePosixPath(str(source_file)[len(COMPLEMENT_PREFIX) :]).name
        return work / COMPLEMENTS_DIR / name
    return root / source_file


def _folio(page: Mapping[str, Any]) -> Folio | None:
    numbering = page.get("numbering") or {}
    value = numbering.get("typed") or numbering.get("value")
    return parse_folio(str(value)) if value else None


def suggest_position(report: Mapping[str, Any], document_id: str, folio: Folio | None) -> int:
    """Posição sugerida (0 = antes da primeira): depois da maior folha menor que a lida.

    Sem número lido, a folha vai para o fim do processo.
    """
    doc = next(d for d in report["documents"] if d["id"] == document_id)
    order = (doc.get("manual_order") or {}).get("page_ids") or doc["page_ids"]
    if folio is None:
        return len(order)
    pages = {p["id"]: p for p in report["pages"]}
    position = 0
    for i, pid in enumerate(order):
        current = _folio(pages[pid])
        if current is not None and current < folio:
            position = i + 1
    return position


def insert_page(
    report: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    document_id: str,
    page: Mapping[str, Any],
    findings: Sequence[Mapping[str, Any]],
    marks_json: Sequence[Mapping[str, Any]],
    position: int,
    overrides: Mapping[str, str] | None = None,
    manual_orders: Mapping[str, ManualOrder] | None = None,
) -> dict[str, Any]:
    """O relatório com a folha nova na posição ``position`` e a sequência resolvida de novo.

    Args:
        report: relatório atual.
        profile: perfil do lote.
        batch_root: pasta do lote original.
        document_id: processo onde a folha entra.
        page: página nova (``page.schema.json``), sem numeração.
        findings: sinalizações de página da folha nova.
        marks_json: marcas de numeração lidas da folha (``numbering.marks``).
        position: posição na ordem de trabalho do processo (0 = antes da primeira).
        overrides: numeração digitada, por página.
        manual_orders: ordem escolhida pelo revisor, por documento (a do processo já
            inclui a folha nova quando o revisor tinha reordenado).
    """
    new: dict[str, Any] = copy.deepcopy(dict(report))
    doc = next(d for d in new["documents"] if d["id"] == document_id)
    entry = dict(page)
    entry["numbering"] = {
        "state": "absent",
        "value": None,
        "confidence": 0.0,
        "previous": [],
        "source": "image",
        "marks": list(marks_json),
    }
    new["pages"].append(entry)
    orders = dict(manual_orders or {})
    if document_id in orders:
        current = list(orders[document_id].page_ids)
        current.insert(min(position, len(current)), entry["id"])
        orders[document_id] = ManualOrder(
            tuple(current), orders[document_id].reviewer, orders[document_id].decided_at
        )
        doc["page_ids"].append(entry["id"])
    else:
        doc["page_ids"].insert(min(position, len(doc["page_ids"])), entry["id"])
    _reindex(new, doc)
    new["findings"] += [dict(f) for f in findings]
    resolved = renumber(new, profile, batch_root, dict(overrides or {}), orders)
    resolved["batch"]["summary"] = recompute_summary(resolved, profile)
    return resolved


def remove_page(
    report: Mapping[str, Any],
    profile: Profile,
    batch_root: Path,
    page_id: str,
    overrides: Mapping[str, str] | None = None,
    manual_orders: Mapping[str, ManualOrder] | None = None,
) -> dict[str, Any]:
    """Desfaz a inserção: tira a folha, as sinalizações dela e resolve a sequência de novo."""
    new: dict[str, Any] = copy.deepcopy(dict(report))
    page = next(p for p in new["pages"] if p["id"] == page_id)
    if not is_complement(page["source_file"]):
        raise ValueError("só uma folha inserida depois pode ser removida")
    new["pages"] = [p for p in new["pages"] if p["id"] != page_id]
    doc = next(d for d in new["documents"] if page_id in d["page_ids"])
    doc["page_ids"] = [pid for pid in doc["page_ids"] if pid != page_id]
    _reindex(new, doc)
    new["findings"] = [f for f in new["findings"] if f["target"]["id"] != page_id]
    orders = {
        k: ManualOrder(tuple(p for p in o.page_ids if p != page_id), o.reviewer, o.decided_at)
        for k, o in (manual_orders or {}).items()
    }
    typed = {k: v for k, v in (overrides or {}).items() if k != page_id}
    resolved = renumber(new, profile, batch_root, typed, orders)
    resolved["batch"]["summary"] = recompute_summary(resolved, profile)
    return resolved


def _reindex(report: dict[str, Any], doc: Mapping[str, Any]) -> None:
    position = {pid: i for i, pid in enumerate(doc["page_ids"])}
    for p in report["pages"]:
        if p["id"] in position:
            p["index"] = position[p["id"]]


def marks_for_report(marks: Sequence[Mark]) -> list[dict[str, Any]]:
    """Marcas no formato de ``numbering.marks`` (para :func:`insert_page`)."""
    from qa_engine.application.serialize import marks_json

    return marks_json(marks)
