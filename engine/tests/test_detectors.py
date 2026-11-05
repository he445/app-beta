import random

import numpy as np
import pytest
import synth

from conftest import blank_150, page_150
from qa_engine.detectors import duplicate_page
from qa_engine.detectors.base import Observation, PageRaster, baseline_of
from qa_engine.detectors.black_borders import DETECTOR as BORDERS
from qa_engine.detectors.blank_page import DETECTOR as BLANK
from qa_engine.detectors.blur import DETECTOR as BLUR
from qa_engine.detectors.exposure import DETECTOR as EXPOSURE
from qa_engine.detectors.features import compute_features
from qa_engine.detectors.low_resolution import DETECTOR as LOWRES
from qa_engine.detectors.registry import params_for
from qa_engine.detectors.skew import DETECTOR as SKEW
from qa_engine.domain.model import CorrectionAction, Severity


def observe(detector, gray, dpi: float | None = 150.0) -> Observation:  # type: ignore[no-untyped-def]
    raster = PageRaster(gray, 1.0, dpi)
    return detector.measure(raster, compute_features(gray), params_for(detector.id, None))


def evaluate(detector, target, batch):  # type: ignore[no-untyped-def]
    obs = [observe(detector, g) for g in batch]
    target_obs = observe(detector, target)
    return detector.evaluate(
        target_obs, baseline_of([*obs, target_obs]), params_for(detector.id, None)
    )


CLEAN = [page_150(seed) for seed in range(1, 7)]


def degraded(fn, seed: int = 99, **kw):  # type: ignore[no-untyped-def]
    page = synth.Page(page_150(seed))
    fn(page, random.Random(seed), **kw)
    return page.gray


def test_clean_pages_raise_nothing() -> None:
    for detector in (BLUR, SKEW, BLANK, BORDERS, EXPOSURE):
        for gray in CLEAN[:3]:
            assert evaluate(detector, gray, CLEAN) is None, detector.id


def test_blur_flags_blurred_page_and_not_dark_one() -> None:
    flag = evaluate(BLUR, degraded(synth.d_blur), CLEAN)
    assert flag is not None
    assert flag.severity is Severity.CRITICAL
    assert flag.correction.action is CorrectionAction.RESCAN
    assert flag.measure < flag.threshold
    assert evaluate(BLUR, degraded(synth.d_dark), CLEAN) is None
    assert evaluate(BLUR, degraded(synth.d_faded), CLEAN) is None


@pytest.mark.parametrize("angle", [-6.0, -2.3, -0.8, 0.7, 1.5, 4.2])
def test_skew_angle_within_tolerance(angle: float) -> None:
    obs = observe(SKEW, degraded(synth.d_skew, angle=angle))
    assert obs.values["angle"] == pytest.approx(angle, abs=0.1)


def test_skew_severity_and_sign() -> None:
    params = params_for("skew", None)
    big = SKEW.evaluate(observe(SKEW, degraded(synth.d_skew, angle=-4.0)), {}, params)
    small = SKEW.evaluate(observe(SKEW, degraded(synth.d_skew, angle=1.5)), {}, params)
    assert big is not None and big.severity is Severity.HIGH
    assert big.correction.params["skew_deg"] == pytest.approx(-4.0, abs=0.1)
    assert small is not None and small.severity is Severity.MEDIUM
    assert SKEW.evaluate(observe(SKEW, degraded(synth.d_skew, angle=0.3)), {}, params) is None


def test_blank_and_near_blank() -> None:
    blank = evaluate(BLANK, blank_150(), CLEAN)
    assert blank is not None and blank.correction.action is CorrectionAction.REMOVE_PAGE
    stamp = blank_150().copy()
    stamp[600:640, 400:520] = 30  # carimbo isolado: nunca removido automaticamente
    near = evaluate(BLANK, stamp, CLEAN)
    assert near is not None and near.correction.action is CorrectionAction.HUMAN_REVIEW


def test_black_borders_crop_fraction() -> None:
    gray = page_150(5).copy()
    gray[:, :35] = 10
    flag = evaluate(BORDERS, gray, CLEAN)
    assert flag is not None
    assert flag.correction.params["crop_fraction"]["left"] == pytest.approx(
        35 / gray.shape[1], abs=1e-3
    )
    assert flag.region is not None and flag.region.w == 35


def test_exposure_dark_and_faded() -> None:
    dark = evaluate(EXPOSURE, degraded(synth.d_dark), CLEAN)
    assert dark is not None
    assert "escura" in dark.message or "sem contraste" in dark.message
    faded = evaluate(EXPOSURE, degraded(synth.d_faded), CLEAN)
    assert faded is not None and faded.correction.action is CorrectionAction.RESCAN


def test_low_resolution() -> None:
    params = params_for("low_resolution", {"min_dpi": 300})
    low = LOWRES.evaluate(observe(LOWRES, CLEAN[0], dpi=200), {}, params)
    assert low is not None and low.measure == 200 and low.confidence == 1.0
    missing = LOWRES.evaluate(observe(LOWRES, CLEAN[0], dpi=None), {}, params)
    assert missing is not None and missing.confidence < 0.5
    assert LOWRES.evaluate(observe(LOWRES, CLEAN[0], dpi=300), {}, params) is None


def test_duplicates() -> None:
    original = page_150(11)
    copy = np.roll(original, 2, axis=1)
    prints = [
        duplicate_page.Fingerprint(
            f"p{i}", duplicate_page.dhash(g), duplicate_page.thumbnail(g), float(i), True
        )
        for i, g in enumerate([original, page_150(12), copy, blank_150()])
    ]
    pairs = duplicate_page.find_duplicates(prints, params_for("duplicate_page", None))
    assert [(p.copy, p.original) for p in pairs] == [("p0", "p2")]


def test_unknown_param_is_rejected() -> None:
    with pytest.raises(ValueError, match="desconhecidos"):
        params_for("blur", {"nao_existe": 1})
