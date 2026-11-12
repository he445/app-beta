"""Base sintética de numeração manuscrita: números escritos à mão no canto da folha.

Gera lotes em que a numeração está **na imagem** (sem ``numbering.json``), para medir o
leitor por imagem, e recortes rotulados para o bench dos reconhecedores. Determinístico
por semente. As fontes manuscritas (OFL) estão em ``tools/synth/fonts``.

Uso::

    uv run --project engine python tools/synth/numbering.py lote --out lote-numeracao
    uv run --project engine python tools/synth/numbering.py recortes --out recortes --n 300
    uv run --project engine python tools/synth/numbering.py sequencia --out lote-sequencia
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import synth
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont

FONTS_DIR = Path(__file__).resolve().parent / "fonts"
PAGE = (1748, 2480)
"""A5 a 300 dpi."""
REGION = (0.60, 0.00, 1.00, 0.18)
"""Canto superior direito, em frações da página: onde o número costuma estar."""


def fonts() -> list[Path]:
    """Fontes manuscritas disponíveis, em ordem estável."""
    return sorted(FONTS_DIR.glob("*.ttf"))


@dataclass
class Written:
    """Um número escrito na folha."""

    text: str
    struck: bool = False
    box: tuple[int, int, int, int] = (0, 0, 0, 0)
    """x, y, largura, altura em pixels da página."""
    font: str = ""


@dataclass
class Sheet:
    """Uma página com o que foi escrito no canto."""

    folio: str | None
    marks: list[Written] = field(default_factory=list)


def draw_number(
    page: Image.Image, text: str, at: tuple[int, int], rng: random.Random, font_path: Path
) -> tuple[int, int, int, int]:
    """Escreve ``text`` com tinta de caneta, leve inclinação e tamanho variado.

    Returns:
        A caixa ``(x, y, w, h)`` do escrito na página.
    """
    # Altura do dígito entre 5 e 8 mm a 300 dpi; cada fonte tem outra proporção.
    target = rng.uniform(5.0, 8.0) / 25.4 * 300
    probe = ImageDraw.Draw(Image.new("L", (1, 1)))
    reference = ImageFont.truetype(str(font_path), 100)
    _, ref_top, _, ref_bottom = probe.textbbox((0, 0), "0123456789", font=reference)
    font = ImageFont.truetype(str(font_path), max(8, round(100 * target / (ref_bottom - ref_top))))
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tile = Image.new("L", (right - left + 24, bottom - top + 24), 0)
    ImageDraw.Draw(tile).text((12 - left, 12 - top), text, font=font, fill=255)
    tile = tile.rotate(rng.uniform(-8, 8), resample=Image.BICUBIC, expand=True, fillcolor=0)
    ink = rng.randint(25, 80)
    x, y = at
    page.paste(Image.new("L", tile.size, ink), (x, y), tile)
    mask = np.asarray(tile) > 40
    ys, xs = np.nonzero(mask)
    return (x + int(xs.min()), y + int(ys.min()), int(np.ptp(xs)) + 1, int(np.ptp(ys)) + 1)


def strike(page: Image.Image, box: tuple[int, int, int, int], rng: random.Random) -> None:
    """Risca o escrito: um traço quase reto pela faixa do meio, ou um X."""
    draw = ImageDraw.Draw(page)
    x, y, w, h = box
    width = max(3, h // 9)
    ink = rng.randint(20, 70)
    if rng.random() < 0.75:
        cy = y + h * rng.uniform(0.40, 0.60)
        slope = h * rng.uniform(-0.15, 0.15)
        draw.line((x - w * 0.08, cy - slope, x + w * 1.08, cy + slope), fill=ink, width=width)
    else:
        draw.line((x - 4, y - 4, x + w + 4, y + h + 4), fill=ink, width=width)
        draw.line((x - 4, y + h + 4, x + w + 4, y - 4), fill=ink, width=width)


def render_sheet(
    sheet: Sheet, rng: random.Random, position: int, total: int, blank: bool = False
) -> NDArray[np.uint8]:
    """Página de texto (sem "fls." impresso) com os números escritos à mão no canto."""
    if blank:
        gray = synth.blank_page(rng, PAGE)
    else:
        gray = synth.text_page(rng, PAGE, 0, total, position, print_folio=False)
    page = Image.fromarray(gray)
    available = fonts()
    x = int(PAGE[0] * rng.uniform(0.70, 0.78))
    y = int(PAGE[1] * rng.uniform(0.025, 0.06))
    for mark in sheet.marks:
        font = available[rng.randrange(len(available))]
        mark.box = draw_number(page, mark.text, (x, y), rng, font)
        mark.font = font.name
        if mark.struck:
            strike(page, mark.box, rng)
        x = mark.box[0] + mark.box[2] + int(PAGE[0] * rng.uniform(0.02, 0.04))
        y += int(PAGE[1] * rng.uniform(-0.006, 0.006))
    return np.asarray(page)


# Cenários (docs/especificacoes/sequencing.md) ----------------------------------------


def _sheets(*folios: str | None) -> list[Sheet]:
    return [Sheet(f, [Written(f)] if f else []) for f in folios]


def scenarios() -> dict[str, dict[str, Any]]:
    """Os oito cenários do leitor por imagem, um documento cada."""
    struck = _sheets("1", "2", None, "4", "5")
    struck[2] = Sheet("3", [Written("7", struck=True), Written("3")])
    two = _sheets("1", "2", None, "4")
    two[2] = Sheet(None, [Written("3"), Written("8")])
    return {
        "01-normal": {"mode": "simple", "sheets": _sheets("1", "2", "3", "4", "5")},
        "02-faltando": {"mode": "simple", "sheets": _sheets("1", "2", "4", "5")},
        "03-fora-de-ordem": {"mode": "simple", "sheets": _sheets("1", "3", "2", "4", "5")},
        "04-riscado": {"mode": "simple", "sheets": struck},
        "05-dois-numeros": {"mode": "simple", "sheets": two},
        "06-frente-e-verso": {
            "mode": "recto_verso",
            "sheets": [
                Sheet("1", [Written("1")]),
                Sheet(None),
                Sheet("2", [Written("2")]),
                Sheet(None),
            ],
        },
        "07-intercalacao": {"mode": "simple", "sheets": _sheets("11", "12", "12-A", "13")},
        "08-sem-numero": {"mode": "simple", "sheets": _sheets("1", "2", None, "4", "5")},
    }


def build_batch(out: Path, seed: int = 20261112) -> dict[str, Any]:
    """Lote com um documento por cenário; ``gabarito.json`` com cada escrito e sua caixa."""
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    key: dict[str, Any] = {"seed": seed, "region": list(REGION), "documents": {}}
    for name, scenario in scenarios().items():
        sheets: list[Sheet] = scenario["sheets"]
        pages = []
        for i, sheet in enumerate(sheets, start=1):
            gray = render_sheet(
                sheet,
                rng,
                i,
                len(sheets),
                blank=sheet.folio is None and not sheet.marks and scenario["mode"] == "recto_verso",
            )
            rel = f"{name}/{i:04d}.tif"
            synth.save_tiff(out / rel, synth.Page(gray), synth.STATIONS[0], 1)
            pages.append(
                {
                    "file": rel,
                    "folio": sheet.folio,
                    "marks": [
                        {"text": m.text, "struck": m.struck, "box": list(m.box), "font": m.font}
                        for m in sheet.marks
                    ],
                }
            )
        key["documents"][name] = {"mode": scenario["mode"], "pages": pages}
    (out / "gabarito.json").write_text(
        json.dumps(key, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    return key


def build_sequence_batch(out: Path, seed: int = 20261114) -> None:
    """Lote para o roteiro da tela de Sequência: um documento de três folhas sem número.

    Nenhuma folha tem número escrito: as três ficam sem numeração e o revisor resolve o
    documento só no teclado.
    """
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    for i in range(1, 4):
        gray = render_sheet(Sheet(None), rng, i, 3)
        synth.save_tiff(out / f"SEM-NUMERO/{i:04d}.tif", synth.Page(gray), synth.STATIONS[0], 1)


# Recortes para o bench ---------------------------------------------------------------


def random_label(rng: random.Random) -> str:
    """Número de folha plausível: 1 a 999, às vezes com letra de intercalação ou verso."""
    n = str(rng.choice([rng.randint(1, 30), rng.randint(1, 200), rng.randint(1, 999)]))
    r = rng.random()
    if r < 0.08:
        return f"{n}-{rng.choice('ABC')}"
    if r < 0.14:
        return f"{n}v"
    return n


def build_crops(
    out: Path, n: int, seed: int = 20261113, struck_ratio: float = 0.2
) -> list[dict[str, Any]]:
    """Recortes de um escrito cada, com rótulo, fonte e se está riscado."""
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    available = fonts()
    labels = []
    for i in range(n):
        text = random_label(rng)
        canvas = Image.fromarray(synth.blank_page(rng, (900, 400)))
        font = available[i % len(available)]
        box = draw_number(canvas, text, (rng.randint(60, 300), rng.randint(60, 160)), rng, font)
        struck = rng.random() < struck_ratio
        if struck:
            strike(canvas, box, rng)
        pad = int(box[3] * rng.uniform(0.15, 0.35))
        x, y, w, h = box
        crop = canvas.crop((max(0, x - pad), max(0, y - pad), x + w + pad, y + h + pad))
        name = f"{i:04d}.png"
        crop.save(out / name)
        labels.append({"file": name, "text": text, "struck": struck, "font": font.name})
    (out / "labels.json").write_text(
        json.dumps(labels, ensure_ascii=False, indent=1) + "\n", "utf-8"
    )
    return labels


def main() -> None:
    """Linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["lote", "recortes", "sequencia"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--n", type=int, default=300, help="quantos recortes")
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()
    if args.mode == "lote":
        build_batch(args.out, args.seed or 20261112)
    elif args.mode == "sequencia":
        build_sequence_batch(args.out, args.seed or 20261114)
    else:
        build_crops(args.out, args.n, args.seed or 20261113)
    print(f"gerado em {args.out}")


if __name__ == "__main__":
    main()
