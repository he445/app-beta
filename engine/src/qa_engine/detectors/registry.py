"""Registro das regras: manifestos e detectores de página.

Uma regra só existe se tiver manifesto aqui, especificação em ``docs/especificacoes/`` e
casos de conformidade; ``tests/test_documentation.py`` cobra isso.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any

import yaml

from qa_engine.detectors import (
    black_borders,
    blank_page,
    blur,
    exposure,
    low_resolution,
    orientation,
    skew,
)
from qa_engine.detectors.base import PageDetector
from qa_engine.domain.model import Severity

RULES: tuple[str, ...] = (
    "corrupted_file",
    "low_resolution",
    "blank_page",
    "orientation",
    "black_borders",
    "blur",
    "skew",
    "exposure",
    "duplicate_page",
    "missing_page",
    "out_of_order",
    "numbering_review",
    "completeness_unverifiable",
)
"""Todas as regras registradas, em ordem estável de execução e relatório."""

PAGE_DETECTORS: tuple[PageDetector, ...] = (
    low_resolution.DETECTOR,
    blank_page.DETECTOR,
    orientation.DETECTOR,
    black_borders.DETECTOR,
    blur.DETECTOR,
    skew.DETECTOR,
    exposure.DETECTOR,
)


@dataclass(frozen=True, slots=True)
class Manifest:
    """Manifesto de uma regra (``contracts/schemas/detector-manifest.schema.json``)."""

    id: str
    version: str
    title: str
    spec: str
    severity: Severity
    defaults: Mapping[str, Any]
    raw: Mapping[str, Any]


def manifest_text(rule: str) -> str:
    """Texto YAML do manifesto empacotado com a regra."""
    return (resources.files("qa_engine.detectors") / rule / "manifest.yaml").read_text("utf-8")


@cache
def manifest(rule: str) -> Manifest:
    """Carrega o manifesto de uma regra registrada."""
    raw = yaml.safe_load(manifest_text(rule))
    defaults = {name: spec["default"] for name, spec in (raw.get("params") or {}).items()}
    return Manifest(
        id=raw["id"],
        version=raw["version"],
        title=raw["title"],
        spec=raw["spec"],
        severity=Severity(raw["severity"]),
        defaults=defaults,
        raw=raw,
    )


def param_problem(rule: str, name: str, value: Any) -> str | None:
    """Por que um valor não serve para um parâmetro (tipo e faixa do manifesto), ou ``None``."""
    spec = (manifest(rule).raw.get("params") or {}).get(name)
    if spec is None:
        return f"parâmetro desconhecido para {rule}: {name}"
    kind = spec.get("type")
    if kind == "boolean":
        ok = isinstance(value, bool)
    elif kind == "integer":
        ok = isinstance(value, int) and not isinstance(value, bool)
    elif kind == "number":
        ok = isinstance(value, (int, float)) and not isinstance(value, bool)
    else:
        ok = True
    names = {"boolean": "verdadeiro ou falso", "integer": "número inteiro", "number": "número"}
    if not ok:
        return f"{rule}.{name}: esperado {names.get(str(kind), kind)}; veio {value!r}"
    if kind in {"integer", "number"}:
        if "minimum" in spec and value < spec["minimum"]:
            return f"{rule}.{name}: esperado ≥ {spec['minimum']}; veio {value!r}"
        if "maximum" in spec and value > spec["maximum"]:
            return f"{rule}.{name}: esperado ≤ {spec['maximum']}; veio {value!r}"
    return None


def params_for(rule: str, overrides: Mapping[str, Any] | None) -> dict[str, Any]:
    """Padrões do manifesto sobrescritos pelos parâmetros do perfil.

    Raises:
        ValueError: parâmetro desconhecido ou fora do tipo e da faixa do manifesto.
    """
    merged = dict(manifest(rule).defaults)
    if overrides:
        unknown = set(overrides) - set(merged)
        if unknown:
            raise ValueError(f"parâmetros desconhecidos para {rule}: {sorted(unknown)}")
        problems = [p for n, v in overrides.items() if (p := param_problem(rule, n, v))]
        if problems:
            raise ValueError("; ".join(problems))
        merged.update(overrides)
    return merged
