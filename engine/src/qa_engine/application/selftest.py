"""Teste de fumaça do programa empacotado: analisar um lote de exemplo e conferir o gabarito.

Roda com processos de análise de verdade (``spawn`` no Windows), que é onde um
executável mal empacotado quebra, e mede o custo por página.
"""

from __future__ import annotations

import json
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qa_engine.application.contracts import validate
from qa_engine.application.profile import Profile
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis

CO_OCCURRENCE: Mapping[str, Sequence[str]] = {
    "blur": ("exposure",),
    "low_resolution": ("exposure",),
}
"""Regras extras aceitas no mesmo alvo de um defeito esperado (as da suíte de conformidade)."""


@dataclass(frozen=True, slots=True)
class SelfTestResult:
    """Resultado do teste de fumaça."""

    ok: bool
    pages: int
    seconds: float
    ms_per_page: float
    budget_ms: float
    errors: tuple[str, ...] = ()
    checks: Mapping[str, bool] = field(default_factory=dict)

    def json(self) -> dict[str, Any]:
        """Uma linha JSON para o log do CI."""
        return {
            "ok": self.ok,
            "pages": self.pages,
            "seconds": round(self.seconds, 3),
            "ms_per_page": round(self.ms_per_page, 1),
            "budget_ms": self.budget_ms,
            "checks": dict(self.checks),
            "errors": list(self.errors),
        }


def compare_with_key(report: Mapping[str, Any], key: Mapping[str, Any]) -> list[str]:
    """Defeitos do gabarito que faltaram e sinalizações graves que não eram esperadas."""
    pages = {p["id"]: p for p in report["pages"]}
    docs = {d["id"]: d["name"] for d in report["documents"]}
    found: dict[tuple[str, str], str] = {}
    for f in report["findings"]:
        target = f["target"]
        name = (
            pages[target["id"]]["source_file"] if target["kind"] == "page" else docs[target["id"]]
        )
        found[(name, f["rule"])] = f["severity"]
    errors: list[str] = []
    accepted: set[tuple[str, str]] = set()
    for item in key.get("defects", []):
        target = item.get("file") or item["document"]
        if (target, item["rule"]) not in found:
            errors.append(f"faltou {item['rule']} em {target}")
        accepted.add((target, item["rule"]))
        accepted.update((target, extra) for extra in CO_OCCURRENCE.get(item["rule"], ()))
    for (target, rule), severity in sorted(found.items()):
        if (target, rule) not in accepted and severity in {"critical", "high"}:
            errors.append(f"sinalização inesperada {rule} ({severity}) em {target}")
    return errors


def run_self_test(
    sample: Path,
    profile: Profile,
    *,
    workers: int = 2,
    budget_ms: float = 1000.0,
    max_factor: float = 3.0,
    extra_checks: Mapping[str, bool] | None = None,
    models_dir: Path | None = None,
) -> SelfTestResult:
    """Analisa o lote de exemplo e confere com ``gabarito.json``.

    Args:
        sample: pasta do lote de exemplo, com ``gabarito.json``.
        profile: perfil da análise.
        workers: processos de análise (2 para exercitar o ``spawn``).
        budget_ms: orçamento por página.
        max_factor: falha se o custo passar de ``max_factor × budget_ms`` (a máquina do CI
            não é a estação; o limite absoluto é conferido na máquina do piloto).
        extra_checks: outras conferências do pacote (interface, perfis, modelos).
        models_dir: modelos embarcados (orientação).
    """
    checks = dict(extra_checks or {})
    errors = [f"conferência falhou: {name}" for name, ok in checks.items() if not ok]
    started = time.perf_counter()
    analysis = run_analysis(
        sample, profile, workers=workers, name="lote-exemplo", models_dir=models_dir
    )
    seconds = time.perf_counter() - started
    report = analysis_json(analysis)
    validate(report, "analysis.schema.json")
    key = json.loads((sample / "gabarito.json").read_text("utf-8"))
    errors += compare_with_key(report, key)
    pages = len(report["pages"])
    ms = 1000.0 * seconds / pages if pages else 0.0
    if ms > max_factor * budget_ms:
        errors.append(f"{ms:.0f} ms por página, acima de {max_factor:g} × {budget_ms:.0f} ms")
    return SelfTestResult(not errors, pages, seconds, ms, budget_ms, tuple(errors), checks)
