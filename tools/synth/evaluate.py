"""Mede a taxa de acerto de um relatório contra o gabarito da base sintética.

Uso::

    uv run --project engine python tools/synth/evaluate.py saida/report.json lote/gabarito.json

Métricas: recall dos críticos, recall geral, precisão por sinalização, precisão
por alvo (uma sinalização extra num alvo que tem defeito real não é alarme
falso), página faltando encontrada e páginas que dispensam revisão.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

CRITICAL_RULES = {"blur", "corrupted_file", "missing_page"}
TARGETS = {
    "critical_recall": 0.98,
    "recall": 0.95,
    "precision": 0.70,
    "no_review_ratio": 0.50,
    "missing_page_recall": 0.95,
}


def evaluate(report: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """Compara sinalizações e gabarito e devolve as métricas."""
    pages = {p["id"]: p for p in report["pages"]}
    docs = {d["id"]: d["name"] for d in report["documents"]}

    def key_of(f: dict[str, Any]) -> tuple[str, str]:
        t = f["target"]
        if t["kind"] == "page":
            p = pages[t["id"]]
            return (f"{p['source_file']}#{p['page_in_file']}", f["rule"])
        return (docs.get(t["id"], t["id"]), f["rule"])

    found = [key_of(f) for f in report["findings"]]
    found_set = set(found)
    expected: list[tuple[set[tuple[str, str]], str]] = []
    defect_targets: set[str] = set()
    for item in truth["defects"]:
        if "file" in item:
            targets = [f"{item['file']}#{item.get('page_in_file', 0)}"]
            targets += [f"{alt}#0" for alt in item.get("alternatives", [])]
        else:
            targets = [item["document"]]
        expected.append(({(t, item["rule"]) for t in targets}, item["rule"]))
        defect_targets.update(targets)
        if "file" in item:
            doc = item["file"].rsplit("/", 1)[0]
            defect_targets.add(doc)
    hits = [bool(keys & found_set) for keys, _ in expected]
    crit = [h for h, (_, rule) in zip(hits, expected, strict=True) if rule in CRITICAL_RULES]
    missing = [h for h, (_, rule) in zip(hits, expected, strict=True) if rule == "missing_page"]
    matched = set().union(*(keys for keys, _ in expected)) if expected else set()
    true_findings = sum(1 for k in found if k in matched)
    target_ok = sum(1 for k in found if k in matched or k[0] in defect_targets)
    misses = [sorted(keys)[0] for (keys, _), h in zip(expected, hits, strict=True) if not h]
    extras = sorted({k for k in found if k not in matched})

    def ratio(a: int, b: int) -> float:
        return a / b if b else 1.0

    return {
        "expected_defects": len(expected),
        "findings": len(found),
        "critical_recall": ratio(sum(crit), len(crit)),
        "recall": ratio(sum(hits), len(hits)),
        "precision": ratio(true_findings, len(found)),
        "precision_by_target": ratio(target_ok, len(found)),
        "missing_page_recall": ratio(sum(missing), len(missing)),
        "no_review_ratio": report["batch"]["summary"]["no_review_ratio"],
        "misses": misses,
        "extras": extras,
    }


def main() -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("report", type=Path)
    parser.add_argument("truth", type=Path)
    parser.add_argument("--json", action="store_true", help="imprimir só o JSON das métricas")
    args = parser.parse_args()
    metrics = evaluate(
        json.loads(args.report.read_text("utf-8")), json.loads(args.truth.read_text("utf-8"))
    )
    if args.json:
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        return 0
    ok = True
    for name, target in TARGETS.items():
        value = metrics[name]
        passed = value >= target
        ok &= passed
        print(f"{'OK ' if passed else 'NÃO'} {name:22} {value:7.1%}  (meta {target:.0%})")
    print(f"    precision_by_target    {metrics['precision_by_target']:7.1%}")
    print(
        f"    {metrics['expected_defects']} defeitos inseridos, {metrics['findings']} sinalizações"
    )
    for miss in metrics["misses"]:
        print(f"    deixou passar: {miss}")
    for extra in metrics["extras"][:30]:
        print(f"    sinalização extra: {extra}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
