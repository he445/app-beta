"""Fixtures compartilhadas: páginas sintéticas pequenas e caminhos do repositório."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest
import yaml
from numpy.typing import NDArray
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "tools" / "synth"))

import synth  # noqa: E402

from qa_engine.application.profile import Profile, profile_from_dict  # noqa: E402

A5_150 = (874, 1240)
"""A5 a 150 dpi: o mesmo tamanho do raster de análise, para testes rápidos."""


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


def page_150(seed: int = 1, folio: int = 1) -> NDArray[np.uint8]:
    """Página de texto sintética já a 150 dpi."""
    return synth.text_page(random.Random(seed), A5_150, folio, 5, folio)


def blank_150(seed: int = 1) -> NDArray[np.uint8]:
    return synth.blank_page(random.Random(seed), A5_150)


def save(path: Path, gray: NDArray[np.uint8], dpi: int = 150, **tags: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    info = {
        271: tags.get("make", "Kodak"),
        272: tags.get("model", "i4250"),
        306: "2026:11:05 10:00:00",
    }
    Image.fromarray(gray).save(path, compression="tiff_deflate", dpi=(dpi, dpi), tiffinfo=info)
    return path


@pytest.fixture
def small_batch(tmp_path: Path) -> Path:
    """Lote de 2 documentos com páginas A5 a 150 dpi (rápidas de analisar).

    DOC1: 6 páginas limpas + 1 inclinada 2,5° + 1 branca.
    DOC2: 3 páginas, a do meio desfocada.
    """
    root = tmp_path / "lote"
    rng = random.Random(7)
    for i in range(1, 7):
        save(root / "CX1/DOC1" / f"{i:04d}.tif", page_150(i, i))
    # Inclinação aplicada a 300 dpi e reduzida, como numa captura real (girar a 150 dpi
    # borra os traços finos e reduz o contraste artificialmente).
    skewed = synth.Page(synth.text_page(random.Random(42), (1748, 2480), 7, 5, 7))
    synth.d_skew(skewed, rng, angle=2.5)
    save(root / "CX1/DOC1/0007.tif", cv2.resize(skewed.gray, A5_150, interpolation=cv2.INTER_AREA))
    save(root / "CX1/DOC1/0008.tif", blank_150())
    for i in range(1, 4):
        gray = page_150(100 + i, i)
        if i == 2:
            p = synth.Page(gray)
            synth.d_blur(p, rng)
            gray = p.gray
        save(root / "CX1/DOC2" / f"{i:04d}.tif", gray)
    return root


@pytest.fixture
def demo_profile_path(repo: Path) -> Path:
    return repo / "profiles" / "demo.yaml"


@pytest.fixture
def test_profile(demo_profile_path: Path) -> Profile:
    """Perfil da demonstração com mínimo de 150 dpi (as páginas de teste são de 150 dpi)."""
    data = yaml.safe_load(demo_profile_path.read_text("utf-8"))
    data["id"] = "test"
    data["resolution"] = {"min_dpi": 150}
    return profile_from_dict(data)
