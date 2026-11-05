"""Perfil do cliente: limiares e regras como configuração (princípio 5)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from qa_engine.application.contracts import validate
from qa_engine.detectors.registry import RULES, params_for
from qa_engine.domain.model import Severity
from qa_engine.domain.scoring import VerdictPolicy
from qa_engine.domain.sequencing import NumberingMode, SequenceParams


@dataclass(frozen=True, slots=True)
class Station:
    """Linha da tabela de estações: liga equipamento ou pasta a um local."""

    location: str
    make: str | None = None
    model: str | None = None
    serial: str | None = None
    folder: str | None = None


@dataclass(frozen=True, slots=True)
class Profile:
    """Perfil validado contra ``contracts/schemas/profile.schema.json``."""

    id: str
    name: str
    organization: str
    min_dpi: float
    verdict: VerdictPolicy
    numbering_enabled: bool
    sequence: SequenceParams
    identifier_pattern: str
    stations: tuple[Station, ...]
    rules: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    """Configuração por regra: ``enabled``, ``severity`` e ``params``."""
    raw: Mapping[str, Any] = field(default_factory=dict)

    def enabled(self, rule: str) -> bool:
        """Se a regra está ligada no perfil (padrão: ligada)."""
        return bool(self.rules.get(rule, {}).get("enabled", True))

    def params(self, rule: str) -> dict[str, Any]:
        """Parâmetros efetivos: manifesto, sobrescrito pelo perfil."""
        overrides = dict(self.rules.get(rule, {}).get("params", {}))
        if rule == "low_resolution":
            overrides.setdefault("min_dpi", self.min_dpi)
        return params_for(rule, overrides)

    def severity_override(self, rule: str) -> Severity | None:
        """Severidade fixada pelo perfil, se houver."""
        value = self.rules.get(rule, {}).get("severity")
        return Severity(value) if value else None


def profile_from_dict(data: Mapping[str, Any]) -> Profile:
    """Valida e converte um perfil já carregado."""
    validate(dict(data), "profile.schema.json")
    rules = dict(data.get("detectors", {}))
    unknown = set(rules) - set(RULES)
    if unknown:
        raise ValueError(f"regras desconhecidas no perfil: {sorted(unknown)}")
    for rule in rules:
        params_for(rule, rules[rule].get("params"))  # falha cedo em parâmetro inválido
    numbering = dict(data.get("numbering", {}))
    verdict = dict(data.get("verdict", {}))
    return Profile(
        id=str(data["id"]),
        name=str(data["name"]),
        organization=str(data["organization"]),
        min_dpi=float(data.get("resolution", {}).get("min_dpi", 300)),
        verdict=VerdictPolicy(
            max_yellow_ratio=float(verdict.get("max_yellow_ratio", 0.02)),
            green_sample_ratio=float(verdict.get("green_sample_ratio", 0.05)),
        ),
        numbering_enabled=bool(numbering.get("enabled", True)),
        sequence=SequenceParams(
            mode=NumberingMode(numbering.get("mode", "simple")),
            min_confidence=float(numbering.get("min_confidence", 0.5)),
            high_confidence=float(numbering.get("high_confidence", 0.85)),
        ),
        identifier_pattern=str(data.get("identifier_pattern", "{batch}-{document}")),
        stations=tuple(Station(**s) for s in data.get("stations", [])),
        rules=rules,
        raw=dict(data),
    )


def load_profile(path: Path) -> Profile:
    """Carrega um perfil YAML ou JSON."""
    return profile_from_dict(yaml.safe_load(path.read_text("utf-8")))


def default_profile() -> Profile:
    """Perfil mínimo com os padrões dos manifestos."""
    return profile_from_dict({"id": "default", "name": "Padrão", "organization": "SOS DOCS"})
