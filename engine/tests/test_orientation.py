"""Orientação da página (ADR-0014): sentido da rotação, faixas, página branca e vista girada."""

from __future__ import annotations

import math
import random
from pathlib import Path

import cv2
import numpy as np
import pytest
import synth

from conftest import blank_150, page_150, save
from qa_engine.application.analyze import PageTask, analyze_page, oriented_view
from qa_engine.application.bulk import is_automatic
from qa_engine.application.corrections import transform
from qa_engine.application.profile import Profile
from qa_engine.detectors import orientation
from qa_engine.detectors.base import PageRaster
from qa_engine.detectors.features import compute_features
from qa_engine.domain.model import CorrectionAction
from qa_engine.ports import OrientationPrediction

TURNS = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
MODELS = Path(__file__).resolve().parents[2] / "models"
HAS_MODELS = (MODELS / "PP-LCNet_x1_0_doc_ori_onnx" / "inference.onnx").is_file()


class Fixed:
    """Classificador falso: sempre a mesma resposta."""

    def __init__(self, angle: int, probability: float) -> None:
        self.prediction = OrientationPrediction(angle, probability)
        self.calls = 0

    def classify(self, gray: np.ndarray) -> OrientationPrediction:
        self.calls += 1
        return self.prediction


def params(**changes: object) -> dict[str, object]:
    from qa_engine.detectors.registry import params_for

    return params_for("orientation", changes)


def flag_for(angle: int, probability: float) -> object:
    gray = page_150(3, 3)
    raster = PageRaster(gray, 1.0, 150, orientation=OrientationPrediction(angle, probability))
    obs = orientation.DETECTOR.measure(raster, compute_features(gray), params())
    return orientation.DETECTOR.evaluate(obs, {}, params())


@pytest.mark.parametrize("angle", [90, 180, 270])
def test_round_trip_is_exact(angle: int) -> None:
    """Girar a página e aplicar a correção proposta devolve o original pixel a pixel."""
    original = page_150(7, 7)
    rotated = cv2.rotate(original, TURNS[angle])
    flag = flag_for(angle, 0.95)
    assert flag is not None and flag.correction.action is CorrectionAction.ROTATE
    fixed = transform(rotated, CorrectionAction.ROTATE, flag.correction.params)
    assert np.array_equal(fixed, original)
    assert np.array_equal(oriented_view(rotated, angle), original)


@pytest.mark.skipif(not HAS_MODELS, reason="modelos não baixados (tools/models/fetch.py)")
@pytest.mark.parametrize("angle", [0, 90, 180, 270])
def test_real_model_locks_the_direction(angle: int) -> None:
    """Com o modelo de verdade: o rótulo é o giro horário que a página sofreu."""
    from qa_engine.adapters.orientation import PaddleOrientationClassifier

    page = synth.text_page(random.Random(11), (1748, 2480), 4, 5, 4)
    gray = page if angle == 0 else cv2.rotate(page, TURNS[angle])
    prediction = PaddleOrientationClassifier(MODELS).classify(gray)
    assert prediction.angle == angle and prediction.probability > 0.9
    assert math.isclose(sum(prediction.probabilities.values()), 1.0, abs_tol=1e-3)


def test_bands_automatic_review_and_nothing() -> None:
    automatic = flag_for(90, 0.95)
    assert automatic is not None and "review" not in automatic.correction.params
    assert automatic.correction.params == {"angle_deg": 270, "detected_deg": 90}
    review = flag_for(180, 0.75)
    assert review is not None and review.correction.params["review"] is True
    assert flag_for(270, 0.55) is None  # abaixo de review_threshold
    assert flag_for(0, 0.99) is None  # de pé


def test_review_band_stays_out_of_fix_all() -> None:
    from qa_engine.application.serialize import finding_json
    from qa_engine.domain.model import Finding, Target, TargetKind

    def finding(flag: object) -> dict[str, object]:
        return finding_json(
            Finding(
                "f",
                Target(TargetKind.PAGE, "p"),
                "orientation",
                "1.0.0",
                flag.severity,
                flag.measure,
                flag.threshold,
                flag.confidence,
                flag.correction,
                flag.message,
            )  # type: ignore[attr-defined]
        )

    assert is_automatic(finding(flag_for(90, 0.95)))
    assert not is_automatic(finding(flag_for(90, 0.70)))


def test_blank_page_is_never_classified(tmp_path: Path, test_profile: Profile) -> None:
    classifier = Fixed(180, 0.99)
    path = save(tmp_path / "branca.tif", blank_150(9))
    task = PageTask(path, 0, (("orientation", params()),), 0.05)
    result = analyze_page(task, classifier=classifier)
    assert classifier.calls == 0
    assert not result.observations["orientation"].eligible


def test_skew_is_measured_on_the_upright_view(tmp_path: Path) -> None:
    """Página inclinada 2,5° e digitalizada de lado: a inclinação é medida de pé."""
    hi = synth.Page(synth.text_page(random.Random(42), (1748, 2480), 7, 5, 7))
    synth.d_skew(hi, random.Random(3), angle=2.5)
    upright = cv2.resize(hi.gray, (874, 1240), interpolation=cv2.INTER_AREA)
    path = save(tmp_path / "de-lado.tif", cv2.rotate(upright, cv2.ROTATE_90_CLOCKWISE))
    from qa_engine.detectors.registry import params_for

    rules = (("orientation", params()), ("skew", params_for("skew", None)))
    with_view = analyze_page(PageTask(path, 0, rules, 0.05), classifier=Fixed(90, 0.95))
    assert abs(with_view.observations["skew"].values["angle"] - 2.5) < 0.3
    without = analyze_page(PageTask(path, 0, rules, 0.05), classifier=Fixed(0, 0.95))
    assert abs(without.observations["skew"].values["angle"] - 2.5) > 1.0  # texto em pé: lixo


def test_other_rules_measure_the_original(tmp_path: Path) -> None:
    from qa_engine.detectors.registry import params_for

    gray = page_150(5, 5).copy()
    gray[:, :35] = 10  # borda preta à esquerda no arquivo
    path = save(tmp_path / "borda.tif", gray)
    rules = (("orientation", params()), ("black_borders", params_for("black_borders", None)))
    a = analyze_page(PageTask(path, 0, rules, 0.05), classifier=Fixed(180, 0.95))
    b = analyze_page(PageTask(path, 0, rules, 0.05), classifier=Fixed(0, 0.95))
    assert a.observations["black_borders"].values == b.observations["black_borders"].values
    assert a.observations["orientation"].values["angle"] == 180
