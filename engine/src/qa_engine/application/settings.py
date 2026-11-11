"""Validação da configuração contra ``contracts/schemas/settings.schema.json``.

Os tipos ficam em :mod:`qa_engine.domain.settings`; a combinação das camadas,
no adaptador da porta ``SettingsSource``.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from qa_engine.application.contracts import validator
from qa_engine.domain.settings import (
    ResolvedSettings,
    Settings,
    SettingsError,
    SettingsProblem,
)

__all__ = [
    "LOCKED",
    "SCHEMA",
    "ResolvedSettings",
    "Settings",
    "SettingsError",
    "SettingsProblem",
    "check_layer",
    "known_keys",
    "settings_from_values",
]

SCHEMA = "settings.schema.json"
LOCKED = "locked"


def _expected(schema: Mapping[str, Any]) -> str:
    """Descreve em português o que o esquema aceita num ponto."""
    if "const" in schema:
        return f'"{schema["const"]}"'
    if "enum" in schema:
        return "um de: " + ", ".join(str(v) for v in schema["enum"])
    for key in ("oneOf", "anyOf"):
        if key in schema:
            return " ou ".join(_expected(s) for s in schema[key])
    kind = schema.get("type")
    kinds = kind if isinstance(kind, list) else [kind]
    names = {
        "string": "texto",
        "integer": "número inteiro",
        "number": "número",
        "boolean": "verdadeiro ou falso",
        "array": "lista",
        "object": "tabela",
        "null": "vazio",
        None: "valor válido",
    }
    text = " ou ".join(names.get(k, str(k)) for k in kinds)
    if "array" in kinds and "items" in schema:
        text += f" de {_expected(schema['items'])}"
    if "minimum" in schema:
        text += f" ≥ {schema['minimum']}"
    if "exclusiveMinimum" in schema:
        text += f" > {schema['exclusiveMinimum']}"
    if "maximum" in schema:
        text += f" ≤ {schema['maximum']}"
    if "pattern" in schema:
        text += f" no padrão {schema['pattern']}"
    if schema.get("minLength"):
        text += " não vazio"
    return text


def known_keys() -> tuple[str, ...]:
    """Chaves de configuração definidas no esquema (sem ``locked``)."""
    properties = validator(SCHEMA).schema["properties"]
    return tuple(k for k in properties if k != LOCKED)


def check_layer(values: Mapping[str, Any], source: str) -> list[SettingsProblem]:
    """Valida uma camada contra o esquema; cada problema diz a chave e a origem."""
    schema = validator(SCHEMA).schema
    problems: list[SettingsProblem] = []
    for error in sorted(validator(SCHEMA).iter_errors(dict(values)), key=lambda e: list(e.path)):
        path = [str(p) for p in error.absolute_path]
        if error.validator == "additionalProperties":
            unknown = sorted(set(error.instance) - set(error.schema.get("properties", {})))
            prefix = ".".join(path)
            problems.extend(
                SettingsProblem(
                    f"{prefix}.{name}" if prefix else name,
                    source,
                    "uma chave conhecida: " + ", ".join(known_keys()),
                    error.instance[name],
                )
                for name in unknown
            )
            continue
        key = path[0] if path else "<raiz>"
        prop = schema["properties"].get(key, {})
        if key == LOCKED:
            prop = prop["properties"]["keys"]
            key = "locked.keys"
        problems.append(SettingsProblem(key, source, _expected(prop), values.get(path[0])))
    unique: dict[tuple[str, str], SettingsProblem] = {}
    for problem in problems:
        unique.setdefault((problem.key, problem.source), problem)
    return list(unique.values())


def _path(value: Any) -> Path | None:
    return Path(os.path.expandvars(str(value))).expanduser() if value else None


def settings_from_values(values: Mapping[str, Any]) -> Settings:
    """Monta :class:`Settings` de um mapa já validado, no formato do esquema."""
    data_dir = _path(values["data_dir"])
    profiles_dir = _path(values["profiles_dir"])
    if data_dir is None or profiles_dir is None:
        raise ValueError("data_dir e profiles_dir são obrigatórios")
    workers = values.get("workers", "auto")
    memory = values.get("max_memory_mb", "auto")
    return Settings(
        data_dir=data_dir,
        profiles_dir=profiles_dir,
        api_token=values.get("api_token") or None,
        cors_origins=tuple(values.get("cors_origins") or ()),
        retention_hours=float(values["retention_days"]) * 24.0,
        max_upload_mb=int(values.get("max_upload_mb", 2048)),
        workers=None if workers == "auto" else int(workers),
        demo_dir=_path(values.get("demo_dir")),
        ui_dir=_path(values.get("ui_dir")),
        output_dir=_path(values.get("output_dir")),
        temp_dir=_path(values.get("temp_dir")),
        allowed_roots=tuple(p for p in map(_path, values.get("allowed_roots") or ()) if p),
        default_station=values.get("default_station") or None,
        batch_settle_seconds=float(values.get("batch_settle_seconds", 0.0)),
        max_memory_mb=None if memory == "auto" else int(memory),
        log_level=str(values.get("log_level", "info")),
    )
