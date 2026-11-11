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

PARAM_SOURCES = ("manifest", "profile", "station")
"""De onde pode vir o valor de um parâmetro, do mais fraco para o mais forte."""


@dataclass(frozen=True, slots=True)
class Station:
    """Linha da tabela de estações: liga equipamento ou pasta a um local.

    ``overrides`` são os ajustes da digitalizadora desta estação, por regra:
    ``{"black_borders": {"params": {"dark_level": 60}}, "duplicate_page": {"enabled": False}}``.
    """

    location: str
    id: str | None = None
    make: str | None = None
    model: str | None = None
    serial: str | None = None
    folder: str | None = None
    overrides: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)


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

    def station(self, station_id: str | None) -> Station | None:
        """Estação pelo identificador (``None`` se não existir no perfil)."""
        if station_id is None:
            return None
        return next((s for s in self.stations if s.id == station_id), None)

    def _station_rule(self, rule: str, station_id: str | None) -> Mapping[str, Any]:
        station = self.station(station_id)
        return station.overrides.get(rule, {}) if station is not None else {}

    def enabled(self, rule: str, station_id: str | None = None) -> bool:
        """Se a regra está ligada: o perfil decide, e a estação pode mudar para as páginas dela."""
        base = bool(self.rules.get(rule, {}).get("enabled", True))
        return bool(self._station_rule(rule, station_id).get("enabled", base))

    def _profile_params(self, rule: str) -> dict[str, Any]:
        overrides = dict(self.rules.get(rule, {}).get("params", {}))
        if rule == "low_resolution":
            overrides.setdefault("min_dpi", self.min_dpi)
        return overrides

    def params(self, rule: str, station_id: str | None = None) -> dict[str, Any]:
        """Parâmetros efetivos: manifesto, sobrescrito pelo perfil e depois pela estação."""
        overrides = self._profile_params(rule)
        overrides.update(self._station_rule(rule, station_id).get("params", {}))
        return params_for(rule, overrides)

    def param_sources(self, rule: str, station_id: str | None = None) -> dict[str, str]:
        """De onde veio cada parâmetro efetivo: ``manifest``, ``profile`` ou ``station``."""
        sources = dict.fromkeys(params_for(rule, None), "manifest")
        sources.update(dict.fromkeys(self._profile_params(rule), "profile"))
        sources.update(
            dict.fromkeys(self._station_rule(rule, station_id).get("params", {}), "station")
        )
        return sources

    def effective_rules(self, station_id: str | None = None) -> list[dict[str, Any]]:
        """Cada regra como fica para uma estação, com a origem de cada valor.

        É o que a tela de configurações mostra: valor, de onde veio e o padrão.
        """
        result: list[dict[str, Any]] = []
        for rule in RULES:
            values = self.params(rule, station_id)
            sources = self.param_sources(rule, station_id)
            defaults = params_for(rule, None)
            station_rule = self._station_rule(rule, station_id)
            if "enabled" in station_rule:
                enabled_source = "station"
            elif "enabled" in self.rules.get(rule, {}):
                enabled_source = "profile"
            else:
                enabled_source = "manifest"
            result.append(
                {
                    "rule": rule,
                    "enabled": self.enabled(rule, station_id),
                    "enabled_source": enabled_source,
                    "params": [
                        {
                            "name": name,
                            "value": values[name],
                            "source": sources[name],
                            "default": defaults[name],
                        }
                        for name in values
                    ],
                }
            )
        return result

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
    stations = tuple(Station(**s) for s in data.get("stations", []))
    seen: set[str] = set()
    for station in stations:
        if station.id is not None:
            if station.id in seen:
                raise ValueError(f"estação repetida no perfil: {station.id!r}")
            seen.add(station.id)
        for rule, override in station.overrides.items():
            try:
                params_for(rule, override.get("params"))
            except ValueError as exc:
                raise ValueError(f"estação {station.id or station.location!r}: {exc}") from exc
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
        stations=stations,
        rules=rules,
        raw=dict(data),
    )


def load_profile(path: Path) -> Profile:
    """Carrega um perfil YAML ou JSON."""
    return profile_from_dict(yaml.safe_load(path.read_text("utf-8")))


def default_profile() -> Profile:
    """Perfil mínimo com os padrões dos manifestos."""
    return profile_from_dict({"id": "default", "name": "Padrão", "organization": "SOS DOCS"})
