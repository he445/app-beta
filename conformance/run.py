"""Executor de conformidade da implementação de referência (Python).

Compara um ``report.json`` com o gabarito de ``expected/`` usando
``tolerances.yaml``. Outra linguagem implementa o mesmo procedimento (ver
``docs/testes/conformidade.md``) e precisa passar 100%.

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
    report: dict[str, Any],
    expected: dict[str, Any],
    tolerances: dict[str, Any],
    disabled: dict[str, set[str | None]] | None = None,
) -> list[str]:
    """Lista de divergências (vazia = conforme).

    Args:
        report: relatório no formato de ``analysis.schema.json``.
        expected: gabarito do lote.
        tolerances: ``tolerances.yaml``.
        disabled: regra → estações em que o perfil a desliga (``None`` = desligada no
            perfil inteiro). Defeito esperado de regra desligada na estação da página
            não é cobrado, e valem as coocorrências de ``when_disabled``.
    """
    disabled = disabled or {}
    station_of = {
        f"{p['source_file']}#{p['page_in_file']}": p.get("station_id") for p in report["pages"]
    }

    def is_off(rule: str, target: str) -> bool:
        where = disabled.get(rule, set())
        return None in where or station_of.get(target) in where

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
        if not hits and all(is_off(item["rule"], t) for t in targets):
            extras = tolerances.get("when_disabled", {}).get(item["rule"], [])
            accepted.update((t, extra) for t in targets for extra in extras)
            continue
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


def disabled_rules(profile: dict[str, Any]) -> dict[str, set[str | None]]:
    """Regras que um perfil desliga: no perfil inteiro (``None``) ou numa estação."""
    off: dict[str, set[str | None]] = {}
    for rule, config in (profile.get("detectors") or {}).items():
        if config.get("enabled") is False:
            off.setdefault(rule, set()).add(None)
    for station in profile.get("stations") or []:
        for rule, config in (station.get("overrides") or {}).items():
            if config.get("enabled") is False:
                off.setdefault(rule, set()).add(station.get("id"))
            elif config.get("enabled") is True:
                off.get(rule, set()).discard(None)
    return off


def main() -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--expected", type=Path, default=HERE / "expected" / "core.json")
    parser.add_argument("--profile", type=Path, help="perfil usado na análise (regras desligadas)")
    args = parser.parse_args()
    profile = yaml.safe_load(args.profile.read_text("utf-8")) if args.profile else {}
    errors = compare(
        json.loads(args.report.read_text("utf-8")),
        json.loads(args.expected.read_text("utf-8")),
        yaml.safe_load((HERE / "tolerances.yaml").read_text("utf-8")),
        disabled_rules(profile),
    )
    for error in errors:
        print(f"NÃO CONFORME: {error}")
    print("conforme" if not errors else f"{len(errors)} divergência(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
