"""Leitor de numeração por imagem: detector, riscado, reconhecedor e integração (T14–T17)."""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest
import yaml
from numpy.typing import NDArray

from qa_engine.application.numbering_image import (
    LONE_STRUCK,
    ImageNumberingReader,
    split_box,
)
from qa_engine.application.profile import Profile, profile_from_dict
from qa_engine.application.review import renumber, report_marks
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis
from qa_engine.detectors.strike import strike_score
from qa_engine.domain.sequencing import (
    NumberingMode,
    PageCandidates,
    SequenceParams,
    resolve,
)
from qa_engine.ports import TextBox, TextReading

REPO = Path(__file__).resolve().parents[2]
MODELS = REPO / "models"
HAS_MODELS = all(
    (MODELS / name).is_dir() for name in ("PP-OCRv5_mobile_det_onnx", "PP-OCRv5_mobile_rec_onnx")
)
needs_models = pytest.mark.skipif(not HAS_MODELS, reason="modelos não baixados")
sys.path.insert(0, str(REPO / "tools" / "synth"))

import numbering as handwriting  # noqa: E402


def digit_patch(text: str, struck: bool = False, h: int = 40) -> NDArray[np.uint8]:
    patch = np.full((h + 30, h * len(text) + 30), 235, np.uint8)
    cv2.putText(patch, text, (12, h + 12), cv2.FONT_HERSHEY_SIMPLEX, h / 28, 30, 3)
    if struck:
        cv2.line(patch, (6, patch.shape[0] // 2), (patch.shape[1] - 6, patch.shape[0] // 2), 30, 4)
    return patch


# Peças, sem modelos ---------------------------------------------------------------


def test_split_box_separates_two_numbers_written_side_by_side() -> None:
    gray = np.full((80, 260), 235, np.uint8)
    cv2.putText(gray, "3", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 20, 4)
    cv2.putText(gray, "8", (160, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 20, 4)
    parts = split_box(gray, TextBox(0, 10, 260, 60, 0.9))
    assert len(parts) == 2 and parts[0].x < parts[1].x
    single = np.full((80, 120), 235, np.uint8)
    cv2.putText(single, "38", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 20, 4)
    assert len(split_box(single, TextBox(0, 10, 120, 60, 0.9))) == 1


def test_strike_score_separates_struck_from_clean() -> None:
    assert strike_score(digit_patch("7", struck=True)) >= 0.6
    assert strike_score(digit_patch("7")) < 0.6
    assert strike_score(np.full((40, 40), 235, np.uint8)) == 0.0


class Boxes:
    """Detector falso: devolve as caixas dadas."""

    def __init__(self, boxes: Sequence[TextBox]) -> None:
        self.boxes = list(boxes)

    def detect(self, gray: NDArray[np.uint8]) -> list[TextBox]:
        return list(self.boxes)


class Texts:
    """Reconhecedor falso: lê os textos dados, um por chamada."""

    name = "falso"

    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)

    def read(self, gray: NDArray[np.uint8]) -> list[TextReading]:
        return [TextReading(self.texts.pop(0), 0.9)]


def page_with(*items: tuple[str, bool]) -> tuple[NDArray[np.uint8], list[TextBox]]:
    """Página 150 dpi com escritos no canto superior direito e as caixas deles."""
    gray = np.full((1240, 874), 235, np.uint8)
    boxes = []
    x = 560
    for text, struck in items:
        patch = digit_patch(text, struck)
        h, w = patch.shape
        gray[40 : 40 + h, x : x + w] = patch
        boxes.append(TextBox(x - int(0.60 * 874) + 8, 48, w - 16, h - 16, 0.9))
        x += w + 30
    return gray, boxes


def test_reader_marks_struck_only_next_to_another_number() -> None:
    gray, boxes = page_with(("7", True), ("3", False))
    read = ImageNumberingReader(Boxes(boxes), Texts("7", "3")).read(gray, 150)
    assert [(m.top.text, m.struck) for m in read.marks] == [("7", True), ("3", False)]
    assert read.written and read.crop_png and read.crop_png.startswith(b"\x89PNG")


def test_lone_number_needs_the_maximum_strike_score() -> None:
    gray, boxes = page_with(("4", False))
    read = ImageNumberingReader(Boxes(boxes), Texts("4")).read(gray, 150)
    assert [(m.top.text, m.struck) for m in read.marks] == [("4", False)]
    assert LONE_STRUCK > 0.9


def test_words_and_tiny_or_wide_boxes_are_not_folios() -> None:
    gray, boxes = page_with(("12", False))
    wide = TextBox(0, 150, 300, 20, 0.9)  # linha de texto impresso
    tiny = TextBox(10, 10, 6, 6, 0.9)  # sujeira
    reader = ImageNumberingReader(Boxes([*boxes, wide, tiny]), Texts("Processo"))
    read = reader.read(gray, 150)
    assert read.marks == () and read.written  # escrito há, número de folha não


def test_empty_region_is_not_written() -> None:
    gray = np.full((1240, 874), 235, np.uint8)
    read = ImageNumberingReader(Boxes([]), Texts()).read(gray, 150)
    assert read.marks == () and not read.written and read.crop_png


def test_profile_numbering_reader_settings(full_profile_path: Path) -> None:
    data = yaml.safe_load(full_profile_path.read_text("utf-8"))
    profile = profile_from_dict(
        {
            **data,
            "numbering": {
                **data["numbering"],
                "regions": [[0.5, 0.0, 1.0, 0.2], [0.0, 0.0, 0.5, 0.2]],
                "struck_threshold": 0.7,
                "recognizer": "trocr-small-handwritten",
                "min_height_mm": 2.5,
                "read_from_image": False,
            },
        }
    )
    reader = profile.numbering_reader
    assert reader.regions == ((0.5, 0.0, 1.0, 0.2), (0.0, 0.0, 0.5, 0.2))
    assert (reader.struck_threshold, reader.recognizer, reader.min_height_mm) == (
        0.7,
        "trocr-small-handwritten",
        2.5,
    )
    assert not reader.enabled


def test_rereading_uses_the_marks_recorded_in_the_report(tmp_path: Path) -> None:
    def page(i: int, readings: list[str]) -> dict[str, Any]:
        return {
            "id": f"p{i}",
            "numbering": {
                "state": "read",
                "source": "image",
                "marks": [
                    {"readings": [{"text": t, "confidence": 0.9}], "struck": False}
                    for t in readings
                ],
            },
        }

    marks, sources = report_marks([page(1, ["1"]), page(2, ["3", "8"]), {"id": "p3"}])
    assert [m.top.text for m in marks["p2"]] == ["3", "8"]
    assert sources == {"p1": "image", "p2": "image"} and "p3" not in marks


# Com os modelos: os oito cenários -------------------------------------------------


@pytest.fixture(scope="module")
def scenario_batch(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("numeracao") / "lote"
    return root, handwriting.build_batch(root)


@pytest.fixture(scope="module")
def reader() -> ImageNumberingReader:
    from qa_engine.adapters.text_detection import OpenCvTextDetector, PaddleTextDetector
    from qa_engine.adapters.text_recognition import recognizer_by_name

    return ImageNumberingReader(
        PaddleTextDetector(MODELS),
        recognizer_by_name(MODELS, "ppocrv5-mobile-rec"),
        fallback=OpenCvTextDetector(),
    )


def resolved(root: Path, key: dict[str, Any], name: str, reader: ImageNumberingReader) -> Any:
    from qa_engine.adapters.images import FileImageSource

    doc = key["documents"][name]
    cands = []
    for i, page in enumerate(doc["pages"]):
        gray = FileImageSource().load(root / page["file"], 0, 150).gray
        cands.append(PageCandidates(f"p{i}", reader.read(gray, 150).marks))
    return resolve(cands, SequenceParams(mode=NumberingMode(doc["mode"])))


@needs_models
@pytest.mark.parametrize(
    ("name", "check"),
    [
        ("01-normal", lambda r: [str(p.value) for p in r.pages] == ["1", "2", "3", "4", "5"]),
        ("02-faltando", lambda r: [[str(f) for f in g.missing] for g in r.gaps] == [["3"]]),
        ("03-fora-de-ordem", lambda r: r.reordered and r.order == ("p0", "p2", "p1", "p3", "p4")),
        ("04-riscado", lambda r: str(r.pages[2].value) == "3" and not r.gaps),
        ("05-dois-numeros", lambda r: r.pages[2].state.value in {"ambiguous", "inferred"}),
        ("06-frente-e-verso", lambda r: not r.gaps and str(r.pages[2].value) == "2"),
        ("07-intercalacao", lambda r: str(r.pages[2].value) == "12-A" and not r.gaps),
        ("08-sem-numero", lambda r: r.pages[2].state.value in {"absent", "inferred"}),
    ],
)
def test_scenarios_through_the_image_reader(
    scenario_batch: tuple[Path, dict[str, Any]],
    reader: ImageNumberingReader,
    name: str,
    check: Any,
) -> None:
    root, key = scenario_batch
    result = resolved(root, key, name, reader)
    assert check(result), [(p.state.value, str(p.value)) for p in result.pages]


@needs_models
def test_analysis_reads_from_the_image_and_records_marks_and_crops(
    tmp_path: Path, test_profile: Profile
) -> None:
    root = tmp_path / "lote"
    handwriting.build_batch(root, seed=7)
    for extra in list(root.iterdir()):
        if extra.is_dir() and extra.name not in {"01-normal", "04-riscado"}:
            for f in extra.iterdir():
                f.unlink()
            extra.rmdir()
    (root / "gabarito.json").unlink()
    analysis = run_analysis(root, test_profile, workers=1, models_dir=MODELS)
    assert analysis.numbering_source == "image"
    report = analysis_json(analysis)
    pages = {p["source_file"]: p for p in report["pages"]}
    struck = pages["04-riscado/0003.tif"]["numbering"]
    assert struck["source"] == "image"
    assert [m["struck"] for m in struck["marks"]] == [True, False]
    assert len(analysis.numbering_crops) == len(report["pages"])
    # Re-resolução com a numeração digitada: o resto continua vindo das marcas gravadas.
    first = pages["01-normal/0001.tif"]["id"]
    again = renumber(report, test_profile, root, {first: "1"})
    by_id = {p["id"]: p["numbering"] for p in again["pages"]}
    assert by_id[first]["source"] == "reviewer"
    assert by_id[pages["04-riscado/0003.tif"]["id"]]["source"] == "image"


def test_sidecar_has_priority_over_the_image(small_batch: Path, test_profile: Profile) -> None:
    (small_batch / "numbering.json").write_text(json.dumps({}), encoding="utf-8")
    analysis = run_analysis(small_batch, test_profile, workers=1, models_dir=MODELS)
    assert analysis.numbering_source == "sidecar" and not analysis.numbering_crops
