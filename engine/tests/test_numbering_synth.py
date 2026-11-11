"""Base sintética de numeração manuscrita e bench dos reconhecedores (T13)."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools"))

import bench_numbering  # noqa: E402
import numbering as handwriting  # noqa: E402


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(folder.rglob("*")):
        if path.is_file():
            h.update(path.relative_to(folder).as_posix().encode())
            h.update(path.read_bytes())
    return h.hexdigest()


def test_generator_is_deterministic_by_seed(tmp_path: Path) -> None:
    a = handwriting.build_crops(tmp_path / "a", 12, seed=5)
    b = handwriting.build_crops(tmp_path / "b", 12, seed=5)
    c = handwriting.build_crops(tmp_path / "c", 12, seed=6)
    assert a == b and digest(tmp_path / "a") == digest(tmp_path / "b")
    assert a != c
    assert {item["font"] for item in a} == {p.name for p in handwriting.fonts()} or len(a) < 7
    assert any(item["struck"] for item in handwriting.build_crops(tmp_path / "d", 40, seed=1))


def test_batch_has_the_eight_scenarios(tmp_path: Path) -> None:
    key = handwriting.build_batch(tmp_path / "lote", seed=3)
    assert list(key["documents"]) == [
        "01-normal",
        "02-faltando",
        "03-fora-de-ordem",
        "04-riscado",
        "05-dois-numeros",
        "06-frente-e-verso",
        "07-intercalacao",
        "08-sem-numero",
    ]
    assert not (tmp_path / "lote" / "numbering.json").exists()  # a numeração está na imagem
    struck = key["documents"]["04-riscado"]["pages"][2]["marks"]
    assert [(m["text"], m["struck"]) for m in struck] == [("7", True), ("3", False)]
    assert key["documents"]["06-frente-e-verso"]["mode"] == "recto_verso"
    for doc in key["documents"].values():
        for page in doc["pages"]:
            for mark in page["marks"]:
                x, y, _, h = mark["box"]
                assert 0.55 * handwriting.PAGE[0] < x and y < 0.18 * handwriting.PAGE[1]
                assert 40 <= h <= 130  # dígito de 5 a 8 mm a 300 dpi, com inclinação


def test_bench_reports_exact_top3_ambiguous_and_time(tmp_path: Path) -> None:
    handwriting.build_crops(tmp_path / "recortes", 20, seed=2)
    crops = bench_numbering.load_crops(tmp_path / "recortes")
    labels = {id(gray): item["text"] for gray, item in crops}

    def oracle(gray: np.ndarray) -> list[tuple[str, float]]:
        return [(labels[id(gray)], 0.9)]

    def second(gray: np.ndarray) -> list[tuple[str, float]]:
        return [("x", 0.9), (labels[id(gray)], 0.4)]

    def nothing(gray: np.ndarray) -> list[tuple[str, float]]:
        return [("fls.", 0.2)]

    perfect = bench_numbering.bench("oráculo", oracle, crops)
    assert (perfect.exact, perfect.top3, perfect.ambiguous) == (1.0, 1.0, 0.0)
    late = bench_numbering.bench("segunda", second, crops)
    assert (late.exact, late.top3) == (0.0, 1.0)
    empty = bench_numbering.bench("nada", nothing, crops)
    assert empty.ambiguous == 1.0 and empty.ms_per_crop >= 0
    text = bench_numbering.table([empty, perfect, late])
    assert text.splitlines()[1].startswith("oráculo")
    assert (
        bench_numbering.canonical("fls. 12") == "12" and bench_numbering.canonical("12-a") == "12-A"
    )
