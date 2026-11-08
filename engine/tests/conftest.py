"""Fixtures compartilhadas: páginas sintéticas pequenas e caminhos do repositório."""

from __future__ import annotations

import json
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
def correction_batch(tmp_path: Path) -> Path:
    """Lote para "Corrigir tudo" e para o lote corrigido (A5, 150 dpi).

    CX1/DOC1: 6 páginas numeradas; a 2 inclinada 2,5°, a 5 com borda preta,
    as páginas 3 e 4 trocadas no arquivo (a numeração diz 4 e 3).
    CX1/DOC2: 4 páginas numeradas 1, 2, 4, 5 (falta a folha 3).
    CX2/DOC3: página em branco, página normal e página desfocada; a última
    foi gravada a 100 dpi (resolução baixa para o perfil de 150 dpi).
    """
    root = tmp_path / "lote-correcao"
    rng = random.Random(11)
    numbering: dict[str, list[dict[str, object]]] = {}

    def mark(rel: str, folio: int) -> None:
        numbering[f"{rel}#0"] = [{"readings": [{"text": str(folio), "confidence": 0.95}]}]

    folios = [1, 2, 4, 3, 5, 6]
    for i, folio in enumerate(folios, start=1):
        rel = f"CX1/DOC1/{i:04d}.tif"
        gray = page_150(200 + folio, folio)
        if i == 2:
            hi = synth.Page(synth.text_page(random.Random(202), (1748, 2480), 2, 6, 2))
            synth.d_skew(hi, rng, angle=2.5)
            gray = cv2.resize(hi.gray, A5_150, interpolation=cv2.INTER_AREA)
        if i == 5:
            gray = gray.copy()
            gray[:, :35] = 10
        save(root / rel, gray)
        mark(rel, folio)
    for i, folio in enumerate([1, 2, 4, 5], start=1):
        rel = f"CX1/DOC2/{i:04d}.tif"
        save(root / rel, page_150(300 + folio, folio))
        mark(rel, folio)
    save(root / "CX2/DOC3/0001.tif", blank_150(5))
    save(root / "CX2/DOC3/0002.tif", page_150(401, 2))
    mark("CX2/DOC3/0002.tif", 2)
    blurred = synth.Page(page_150(402, 3))
    synth.d_blur(blurred, rng)
    save(root / "CX2/DOC3/0003.tif", blurred.gray, dpi=100)
    mark("CX2/DOC3/0003.tif", 3)
    (root / "numbering.json").write_text(json.dumps({"pages": numbering}), encoding="utf-8")
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
