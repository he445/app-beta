import json
from pathlib import Path

import pytest
import yaml
from jsonschema import Draft202012Validator

from qa_engine.application.contracts import ContractError, validate
from qa_engine.application.profile import load_profile
from qa_engine.detectors.registry import RULES, manifest_text


def schema_files(repo: Path) -> list[Path]:
    return sorted((repo / "contracts/schemas").glob("*.schema.json"))


def test_schemas_are_valid_2020_12(repo: Path) -> None:
    for path in schema_files(repo):
        schema = json.loads(path.read_text("utf-8"))
        Draft202012Validator.check_schema(schema)
        assert schema["$id"] == path.name


def test_openapi_refs_resolve(repo: Path) -> None:
    spec = yaml.safe_load((repo / "contracts/openapi.yaml").read_text("utf-8"))
    assert spec["openapi"].startswith("3.1")
    refs: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            if "$ref" in node:
                refs.append(node["$ref"])
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(spec)
    for ref in refs:
        if ref.startswith("#/"):
            target: object = spec
            for part in ref[2:].split("/"):
                assert isinstance(target, dict)
                target = target[part]
        else:
            assert (repo / "contracts" / ref).is_file(), ref
    operation_ids = [
        op["operationId"]
        for p in spec["paths"].values()
        for op in p.values()
        if isinstance(op, dict) and "operationId" in op
    ]
    assert len(operation_ids) == len(set(operation_ids))


@pytest.mark.parametrize("rule", RULES)
def test_manifests_follow_schema(rule: str) -> None:
    data = yaml.safe_load(manifest_text(rule))
    validate(data, "detector-manifest.schema.json")
    assert data["id"] == rule


def test_profiles_validate(repo: Path) -> None:
    for path in (repo / "profiles").glob("*.yaml"):
        load_profile(path)


def test_profile_rejects_unknown_rule() -> None:
    with pytest.raises(ContractError):
        validate(
            {"id": "x", "name": "x", "organization": "x", "detectors": {"foo": {}}},
            "profile.schema.json",
        )


def test_finding_example_from_add_validates() -> None:
    finding = {
        "id": "6f1c2b8e-4a77-5d0e-9c3a-2f3b9d1e7a10",
        "target": {"kind": "page", "id": "p1"},
        "rule": "blur",
        "rule_version": "1.0.0",
        "severity": "critical",
        "measure": 0.06,
        "threshold": 0.68,
        "confidence": 0.95,
        "message": "Nitidez baixa.",
        "region": {"x": 0, "y": 0, "w": 10, "h": 10},
        "correction": {"kind": "physical", "action": "rescan", "description": "x", "params": {}},
    }
    validate(finding, "finding.schema.json")
    with pytest.raises(ContractError):
        validate({**finding, "severity": "grave"}, "finding.schema.json")


FOCUS = {"missing_page", "blank_page", "skew", "blur"}
SUPPORT = {"out_of_order", "numbering_review", "completeness_unverifiable", "corrupted_file"}


def test_demo_profile_focuses_on_the_four_cases(repo: Path) -> None:
    """ADR-0010: a demonstração mostra faltando, em branco, torta e sem nitidez."""
    from qa_engine.detectors.registry import RULES

    demo = load_profile(repo / "profiles/demo.yaml")
    full = load_profile(repo / "profiles/completo.yaml")
    assert {r for r in RULES if demo.enabled(r)} == FOCUS | SUPPORT
    assert {r for r in RULES if full.enabled(r)} == set(RULES)
