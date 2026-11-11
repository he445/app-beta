"""Suíte de conformidade: o lote `core` gerado tem de casar com o gabarito versionado."""

import json
import sys
from pathlib import Path

import pytest
import synth
import yaml

from qa_engine.application.profile import load_profile
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis


@pytest.fixture(scope="session")
def core_batch(repo: Path) -> Path:
    root = repo / "conformance/fixtures/core"
    expected = json.loads((repo / "conformance/expected/core.json").read_text("utf-8"))
    gabarito = root / "gabarito.json"
    if not gabarito.is_file() or json.loads(gabarito.read_text("utf-8")) != expected:
        synth.build(root, synth.conformance_plan(), expected["seed"], (1748, 2480))
    return root


@pytest.mark.conformance
def test_generator_matches_expected(repo: Path, core_batch: Path) -> None:
    generated = json.loads((core_batch / "gabarito.json").read_text("utf-8"))
    expected = json.loads((repo / "conformance/expected/core.json").read_text("utf-8"))
    assert generated == expected, "o gerador mudou: atualize conformance/expected/core.json"


@pytest.mark.conformance
@pytest.mark.parametrize("profile_id", ["completo", "demo", "sos-piloto"])
def test_reference_engine_is_conformant(repo: Path, core_batch: Path, profile_id: str) -> None:
    """O motor passa a suíte com cada perfil; regra desligada no perfil não é cobrada."""
    sys.path.insert(0, str(repo / "conformance"))
    from run import compare, disabled_rules

    models = repo / "models"
    if not (models / "PP-LCNet_x1_0_doc_ori_onnx" / "inference.onnx").is_file():
        pytest.skip("modelos não baixados: uv run --project engine python tools/models/fetch.py")
    path = repo / "profiles" / f"{profile_id}.yaml"
    report = analysis_json(run_analysis(core_batch, load_profile(path), models_dir=models))
    errors = compare(
        report,
        json.loads((repo / "conformance/expected/core.json").read_text("utf-8")),
        yaml.safe_load((repo / "conformance/tolerances.yaml").read_text("utf-8")),
        disabled_rules(yaml.safe_load(path.read_text("utf-8"))),
    )
    assert errors == []
