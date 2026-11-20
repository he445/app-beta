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
    assert flag_for(0, 0.55) is None  # abaixo de review_threshold e 0° acima do piso
    assert flag_for(0, 0.99) is None  # de pé
    uncertain = flag_for(270, 0.55)  # P(0°) ≤ 0,45: não dá para dizer que está de pé
    assert uncertain is not None and uncertain.correction.params["uncertain"] is True


def spread_flag(probabilities: dict[int, float], **changes: object) -> object:
    angle = max(probabilities, key=lambda a: probabilities[a])
    prediction = OrientationPrediction(angle, probabilities[angle], probabilities)
    gray = page_150(3, 3)
    raster = PageRaster(gray, 1.0, 150, orientation=prediction)
    obs = orientation.DETECTOR.measure(raster, compute_features(gray), params(**changes))
    return orientation.DETECTOR.evaluate(obs, {}, params(**changes))


def test_spread_probabilities_are_uncertain_not_upright() -> None:
    """P2 do relatório de testes: "não sei" vai para revisão, não vira "está certa"."""
    flag = spread_flag({0: 0.28, 90: 0.26, 180: 0.24, 270: 0.22})
    assert flag is not None
    assert flag.correction.params == {
        "angle_deg": 270,
        "detected_deg": 90,
        "review": True,
        "uncertain": True,
    }
    assert flag.measure == 0.28 and flag.threshold == 0.5
    assert flag.message.startswith("Orientação incerta")
    # 0° mais provável, mas abaixo do piso: sugere a rotação mais provável.
    top_upright = spread_flag({0: 0.46, 90: 0.05, 180: 0.04, 270: 0.45})
    assert top_upright is not None and top_upright.correction.params["detected_deg"] == 270
    # 0° acima do piso: nada.
    assert spread_flag({0: 0.55, 90: 0.15, 180: 0.15, 270: 0.15}) is None
    # Rotação acima de review_threshold: sugestão normal, não incerta.
    normal = spread_flag({0: 0.10, 90: 0.70, 180: 0.10, 270: 0.10})
    assert normal is not None and "uncertain" not in normal.correction.params
    # Piso zero desliga a orientação incerta.
    assert spread_flag({0: 0.28, 90: 0.26, 180: 0.24, 270: 0.22}, upright_min_probability=0) is None


def test_uncertain_never_enters_fix_all_nor_applies_to_low_ink() -> None:
    from qa_engine.detectors.base import Observation

    flag = spread_flag({0: 0.10, 90: 0.40, 180: 0.30, 270: 0.20})
    assert flag is not None and flag.correction.params["review"] is True
    # Pouca tinta (carimbo, rubrica): o modelo espalha sem haver texto; nada.
    obs = Observation(
        {"angle": 180.0, "probability": 0.87, "upright_probability": 0.06},
        extra={"low_ink": True, "runner_up": (180, 0.87)},
    )
    assert orientation.DETECTOR.evaluate(obs, {}, params()) is None


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


def sparse_150() -> np.ndarray:
    """Bilhete curto: tinta entre página branca e o limite de pouca tinta."""
    gray = blank_150(9).copy()
    cv2.putText(gray, "manuscrito curto", (300, 600), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 1.6, 20, 3)
    return gray


def test_low_ink_page_is_classified_but_only_flags_high_confidence_for_review(
    tmp_path: Path,
) -> None:
    """P1 do relatório de testes: bilhete curto girado não pode passar calado."""
    gray = sparse_150()
    coverage = compute_features(gray).ink_coverage
    assert params()["blank_ink_coverage"] <= coverage < params()["min_ink_coverage"]
    path = save(tmp_path / "bilhete.tif", gray)

    def flag(angle: int, probability: float) -> object:
        classifier = Fixed(angle, probability)
        result = analyze_page(
            PageTask(path, 0, (("orientation", params()),), 0.05), classifier=classifier
        )
        assert classifier.calls == 1
        obs = result.observations["orientation"]
        assert obs.eligible and obs.extra["low_ink"] is True
        return orientation.DETECTOR.evaluate(obs, {}, params())

    high = flag(180, 0.93)
    assert high is not None
    assert high.correction.params == {
        "angle_deg": 180,
        "detected_deg": 180,
        "review": True,
        "low_ink": True,
    }
    assert high.threshold == params()["auto_threshold"]
    assert flag(180, 0.87) is None  # abaixo de auto_threshold: carimbo (CX001/DOC0007)
    assert flag(0, 0.99) is None


def test_low_ink_rotation_never_enters_fix_all() -> None:
    from qa_engine.detectors.base import Observation

    obs = Observation({"angle": 90.0, "probability": 0.99}, extra={"low_ink": True})
    flag = orientation.DETECTOR.evaluate(obs, {}, params())
    assert flag is not None and flag.correction.params["review"] is True


def test_skip_blank_off_classifies_low_ink_like_any_page() -> None:
    gray = sparse_150()
    raster = PageRaster(gray, 1.0, 150, orientation=OrientationPrediction(90, 0.70))
    changed = params(skip_blank=False)
    obs = orientation.DETECTOR.measure(raster, compute_features(gray), changed)
    flag = orientation.DETECTOR.evaluate(obs, {}, changed)
    assert flag is not None and "low_ink" not in flag.correction.params


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


class Sequence:
    """Classificador falso: responde em ordem, uma resposta por chamada."""

    def __init__(self, *answers: tuple[int, float]) -> None:
        self.answers = [OrientationPrediction(a, p) for a, p in answers]
        self.calls = 0

    def classify(self, gray: np.ndarray) -> OrientationPrediction:
        self.calls += 1
        return self.answers.pop(0)


def _skewed(tmp_path: Path, angle: float) -> Path:
    hi = synth.Page(synth.text_page(random.Random(42), (1748, 2480), 7, 5, 7))
    synth.d_skew(hi, random.Random(3), angle=angle)
    return save(tmp_path / f"inclinada-{angle}.tif", cv2.resize(hi.gray, (874, 1240)))


def test_strong_skew_also_classifies_the_straightened_view(tmp_path: Path) -> None:
    """Com inclinação forte, vale a leitura mais confiante entre a vista crua e a endireitada."""
    from qa_engine.detectors.registry import params_for

    rules = (("orientation", params()), ("skew", params_for("skew", None)))
    path = _skewed(tmp_path, 5.0)
    wrong_then_right = Sequence((180, 0.9), (0, 0.93))
    result = analyze_page(PageTask(path, 0, rules, 0.05), classifier=wrong_then_right)
    assert wrong_then_right.calls == 2
    assert result.observations["orientation"].values["angle"] == 0
    right_then_worse = Sequence((0, 0.77), (180, 0.58))
    kept = analyze_page(PageTask(path, 0, rules, 0.05), classifier=right_then_worse)
    assert kept.observations["orientation"].values["angle"] == 0
    # De pé, a inclinação medida antes de classificar é a que vale.
    assert abs(kept.observations["skew"].values["angle"] - 5.0) < 0.3


def test_mild_skew_classifies_once(tmp_path: Path) -> None:
    from qa_engine.detectors.registry import params_for

    rules = (("orientation", params()), ("skew", params_for("skew", None)))
    once = Fixed(0, 0.95)
    analyze_page(PageTask(_skewed(tmp_path, 1.0), 0, rules, 0.05), classifier=once)
    assert once.calls == 1


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


# Rotação escolhida pelo revisor (T12) ---------------------------------------------


def test_manual_rotation_is_an_audited_decision_and_goes_to_the_corrected_batch(
    tmp_path: Path, full_profile_path: Path, correction_batch: Path
) -> None:
    import io
    import time
    import zipfile

    import yaml
    from fastapi.testclient import TestClient
    from PIL import Image

    from qa_engine.application.contracts import validate
    from qa_engine.entrypoints.http.app import create_app
    from qa_engine.entrypoints.http.settings import Settings

    profiles = tmp_path / "profiles"
    profiles.mkdir()
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    data["resolution"] = {"min_dpi": 100}
    (profiles / "demo.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=None,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
    )
    files = [
        (
            "files",
            (f"lote/{p.relative_to(correction_batch).as_posix()}", p.read_bytes(), "image/tiff"),
        )
        for p in sorted(correction_batch.rglob("*.tif"))
    ]
    with TestClient(create_app(settings)) as client:
        batch_id = client.post("/batches", files=files).json()["id"]
        for _ in range(200):
            if client.get(f"/batches/{batch_id}").json()["status"] == "analyzed":
                break
            time.sleep(0.1)
        report = client.get(f"/batches/{batch_id}/report").json()
        page = next(p for p in report["pages"] if p["source_file"] == "CX1/DOC2/0001.tif")

        r = client.put(f"/pages/{page['id']}/rotation", json={"angle_deg": 90, "reviewer": "maria"})
        assert r.status_code == 200, r.text
        finding = r.json()["finding"]
        validate(finding, "finding.schema.json")
        assert (
            finding["rule"] == "orientation" and finding["correction"]["params"]["manual"] is True
        )
        assert (
            finding["decision"]["action"] == "correct"
            and finding["decision"]["reviewer"] == "maria"
        )

        def corrected() -> np.ndarray:
            png = client.get(f"/pages/{page['id']}/image", params={"variant": "corrected"}).content
            return np.asarray(Image.open(io.BytesIO(png)))

        original = np.asarray(Image.open(correction_batch / "CX1/DOC2/0001.tif"))
        assert np.array_equal(corrected(), cv2.rotate(original, cv2.ROTATE_90_CLOCKWISE))

        # Trocar o ângulo regrava a cópia (não reaproveita a de 90°).
        r = client.put(
            f"/pages/{page['id']}/rotation", json={"angle_deg": 270, "reviewer": "maria"}
        )
        assert r.json()["finding"]["id"] == finding["id"]
        assert np.array_equal(corrected(), cv2.rotate(original, cv2.ROTATE_90_COUNTERCLOCKWISE))

        plan = client.get(f"/batches/{batch_id}/corrected-plan").json()
        item = next(p for d in plan["documents"] for p in d["pages"] if p["page_id"] == page["id"])
        assert item["corrected"] and item["changes"][0]["text"] == "girada 270°"
        assert item["changes"][0]["decided_by"] == "maria"

        # A página girada vai girada no zip, e a decisão vai no registro de decisões.
        for missing in client.get(f"/batches/{batch_id}/findings").json():
            if missing["rule"] == "missing_page":
                client.post(
                    f"/findings/{missing['id']}/decision",
                    json={"action": "reject", "reviewer": "maria"},
                )
        saved = client.post(
            f"/batches/{batch_id}/corrected-batch", json={"reviewer": "maria"}
        ).json()
        archive = zipfile.ZipFile(io.BytesIO(client.get(saved["download"]).content))
        rotated = np.asarray(Image.open(io.BytesIO(archive.read(item["target_file"]))))
        assert rotated.shape == original.shape[::-1]
        decisions = archive.read("decisions.csv").decode()
        assert "rotate" not in decisions and "orientation" in decisions and "maria" in decisions

        # Não girar: aprova a sinalização (fica auditado) e a cópia volta ao original.
        r = client.put(f"/pages/{page['id']}/rotation", json={"angle_deg": 0, "reviewer": "joão"})
        assert r.json()["finding"]["decision"]["action"] == "approve"
        assert (
            client.get(f"/pages/{page['id']}/image", params={"variant": "corrected"}).status_code
            == 404
        )
        other = next(p for p in report["pages"] if p["source_file"] == "CX1/DOC2/0002.tif")
        assert (
            client.put(
                f"/pages/{other['id']}/rotation", json={"angle_deg": 0, "reviewer": "x"}
            ).status_code
            == 409
        )


# Bench de orientação (tools/bench_orientation.py) ------------------------------------


def test_bench_outcomes_follow_the_report(tmp_path: Path) -> None:
    """Desfechos do bench: correta, automática certa, silenciosa e ângulo errado."""
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
    import bench_orientation as bench

    assert bench.classify_outcome(0, 0, False, False) == "upright_ok"
    assert bench.classify_outcome(90, 90, False, False) == "rotated_auto_ok"
    assert bench.classify_outcome(90, 0, False, False) == "rotated_silent"
    assert bench.classify_outcome(180, 90, True, False) == "rotated_review_wrong"
    assert bench.classify_outcome(0, 180, True, False) == "upright_review"
    assert bench.classify_outcome(270, 0, True, True) == "rotated_uncertain"

    save(tmp_path / "a.tif", page_150(1, 1))
    save(tmp_path / "b.tif", page_150(2, 2))
    labels = tmp_path / "gabarito.csv"
    labels.write_text("arquivo,angulo_real\na.tif,90\nb.tif,180\n", "utf-8")
    outcomes = bench.bench(
        tmp_path, bench.load_labels(labels), params(), None, classifier=Fixed(90, 0.95)
    )
    assert [o.outcome for o in outcomes] == ["rotated_auto_ok", "rotated_auto_wrong"]
    data = bench.summary(outcomes)
    assert data["automatic_wrong"] == 1 and data["silent"] == 0
    assert data["per_angle"]["90"] == {"hits": 1, "n": 1}
    assert "| Girada, corrigida automaticamente | 1 |" in bench.table(data)
