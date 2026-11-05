"""Executor de conformidade da implementação de referência (Python).

Compara um ``report.json`` com o gabarito de ``expected/`` usando
``tolerances.yaml``. Outra linguagem implementa o mesmo procedimento (ver
``conformance/README.md``) e precisa passar 100%.

Uso::

    uv run --project engine python conformance/run.py saida/report.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

HERE = Path(__file__).resolve().parent


def _get(obj: Any, dotted: str) -> Any:
    for part in dotted.split("."):
        obj = obj[part]
    return obj


def compare(
    report: dict[str, Any], expected: dict[str, Any], tolerances: dict[str, Any]
) -> list[str]:
    """Lista de divergências (vazia = conforme)."""
    pages = {p["id"]: p for p in report["pages"]}
    docs = {d["id"]: d["name"] for d in report["documents"]}
    found: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for f in report["findings"]:
        t = f["target"]
        if t["kind"] == "page":
            p = pages[t["id"]]
            key = (f"{p['source_file']}#{p['page_in_file']}", f["rule"])
        else:
            key = (docs[t["id"]], f["rule"])
        found.setdefault(key, []).append(f)

    errors: list[str] = []
    accepted: set[tuple[str, str]] = set()
    co = tolerances.get("co_occurrence", {})
    for item in expected["defects"]:
        if "file" in item:
            targets = [f"{item['file']}#{item.get('page_in_file', 0)}"]
            targets += [f"{a}#0" for a in item.get("alternatives", [])]
        else:
            targets = [item["document"]]
        hits = [(t, item["rule"]) for t in targets if (t, item["rule"]) in found]
        if not hits:
            errors.append(f"faltou {item['rule']} em {targets[0]}")
            continue
        accepted.update(hits)
        accepted.update((t, extra) for t in targets for extra in co.get(item["rule"], []))
        tol = tolerances.get("measures", {}).get(item["rule"])
        if tol:
            got = float(_get(found[hits[0]][0], tol["field"]))
            want = float(_get(item, tol["expected"]))
            limit = tol.get("abs", abs(want) * tol.get("rel", 0.0))
            if abs(got - want) > limit:
                errors.append(
                    f"{item['rule']} em {targets[0]}: {tol['field']} = {got:.4f}, "
                    f"esperado {want:.4f} ± {limit:.4f}"
                )
    for key in sorted(set(found) - accepted):
        errors.append(f"sinalização inesperada {key[1]} em {key[0]}")
    return errors


def main() -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected", type=Path, default=HERE / "expected" / "core.json")
    args = parser.parse_args()
    errors = compare(
        json.loads(args.report.read_text("utf-8")),
        json.loads(args.expected.read_text("utf-8")),
        yaml.safe_load((HERE / "tolerances.yaml").read_text("utf-8")),
    )
    for error in errors:
        print(f"NÃO CONFORME: {error}")
    print("conforme" if not errors else f"{len(errors)} divergência(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
