"""Acesso aos esquemas de ``contracts/`` e validação contra eles (ADR-0002)."""

from __future__ import annotations

import json
import os
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


class ContractError(ValueError):
    """Documento inválido segundo o contrato."""


def contracts_dir() -> Path:
    """Localiza ``contracts/``: variável ``QA_CONTRACTS_DIR`` ou diretórios ancestrais."""
    env = os.environ.get("QA_CONTRACTS_DIR")
    if env:
        return Path(env)
    for base in (Path(__file__).resolve(), Path.cwd().resolve()):
        for parent in (base, *base.parents):
            candidate = parent / "contracts" / "schemas"
            if candidate.is_dir():
                return parent / "contracts"
    raise FileNotFoundError("diretório contracts/ não encontrado; defina QA_CONTRACTS_DIR")


@cache
def _registry() -> Registry[Any]:
    resources = []
    for path in sorted((contracts_dir() / "schemas").glob("*.schema.json")):
        schema = json.loads(path.read_text("utf-8"))
        resources.append((schema["$id"], Resource.from_contents(schema)))
    return Registry().with_resources(resources)


@cache
def validator(schema_id: str) -> Draft202012Validator:
    """Validador para um esquema pelo ``$id`` (ex.: ``finding.schema.json``)."""
    schema = _registry().contents(schema_id)
    return Draft202012Validator(schema, registry=_registry())


def validate(instance: Any, schema_id: str) -> None:
    """Levanta :class:`ContractError` com todas as violações encontradas."""
    errors = sorted(validator(schema_id).iter_errors(instance), key=lambda e: list(e.path))
    if errors:
        detail = "; ".join(f"{'/'.join(map(str, e.path)) or '<raiz>'}: {e.message}" for e in errors)
        raise ContractError(f"{schema_id}: {detail}")
