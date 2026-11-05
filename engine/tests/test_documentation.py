"""Princípio 7: sem documentação, não está pronto. A CI falha se faltar algo."""

import re
from pathlib import Path

import pytest
import yaml

from qa_engine.detectors.registry import PAGE_DETECTORS, RULES, manifest

TEMPLATE_HEADINGS = [
    "## Objetivo",
    "## Entrada",
    "## Algoritmo",
    "## Parâmetros",
    "## Saída",
    "## Falhas conhecidas",
    "## Casos de conformidade",
    "## Histórico de versões",
]
SEQUENCE_RULES = {"missing_page", "out_of_order", "numbering_review", "completeness_unverifiable"}


@pytest.mark.parametrize("rule", RULES)
def test_every_rule_has_spec(repo: Path, rule: str) -> None:
    m = manifest(rule)
    spec = repo / m.spec
    assert spec.is_file(), f"{rule}: falta {m.spec}"
    text = spec.read_text("utf-8")
    if rule in SEQUENCE_RULES:
        assert f"`{rule}`" in text
        return
    assert text.startswith(f"# {rule}:"), f"{m.spec} deve começar com '# {rule}: ...'"
    assert f"Versão: {m.version}" in text, f"{m.spec}: versão diferente do manifesto"
    for heading in TEMPLATE_HEADINGS:
        assert heading in text, f"{m.spec}: falta a seção '{heading}'"
    for name in m.defaults:
        assert f"`{name}`" in text, f"{m.spec}: parâmetro {name} não documentado"


@pytest.mark.parametrize("rule", RULES)
def test_every_rule_has_conformance_case(repo: Path, rule: str) -> None:
    expected = (repo / "conformance/expected/core.json").read_text("utf-8")
    cases = (repo / "conformance/fixtures/sequencing/cases.json").read_text("utf-8")
    assert f'"{rule}"' in expected or f'"{rule}"' in cases, f"{rule}: sem caso de conformidade"


def test_page_detectors_are_registered_rules() -> None:
    assert {d.id for d in PAGE_DETECTORS} <= set(RULES)


def test_adrs_follow_madr(repo: Path) -> None:
    adrs = sorted((repo / "docs/adr").glob("[0-9][0-9][0-9][0-9]-*.md"))
    assert len(adrs) >= 6
    for path in adrs:
        text = path.read_text("utf-8")
        for heading in ("## Contexto", "## Decisão", "## Consequências"):
            assert heading in text, f"{path.name}: falta {heading}"
        assert re.search(r"^Status: (proposto|aceito|substituído|descontinuado)", text, re.M)


def test_glossary_covers_domain_terms(repo: Path) -> None:
    text = (repo / "docs/glossary.md").read_text("utf-8")
    for term in (
        "Batch",
        "Document",
        "Page",
        "Finding",
        "Correction",
        "Decision",
        "Profile",
        "Severity",
        "Verdict",
        "SourceDefect",
        "ReworkOrder",
    ):
        assert term in text


def test_changelog_has_unreleased(repo: Path) -> None:
    assert "## [Não lançado]" in (repo / "CHANGELOG.md").read_text("utf-8")


def test_mkdocs_nav_files_exist(repo: Path) -> None:
    config = yaml.safe_load((repo / "mkdocs.yml").read_text("utf-8").replace("!!python", "#"))
    docs = repo / "docs"

    def walk(node: object) -> None:
        if isinstance(node, str) and node.endswith(".md"):
            assert (docs / node).is_file(), f"mkdocs.yml aponta para {node}, que não existe"
        elif isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(config["nav"])


def test_relative_markdown_links_resolve(repo: Path) -> None:
    pattern = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)")
    files = [
        *repo.glob("*.md"),
        *repo.glob("docs/**/*.md"),
        *repo.glob("spec/**/*.md"),
        *repo.glob("conformance/*.md"),
        *repo.glob("tools/**/*.md"),
        *repo.glob("deploy/*.md"),
        *repo.glob("ui/*.md"),
    ]
    broken = []
    for path in files:
        for target in pattern.findall(path.read_text("utf-8")):
            if not (path.parent / target).exists():
                broken.append(f"{path.relative_to(repo)} → {target}")
    assert not broken, "links quebrados:\n" + "\n".join(broken)
