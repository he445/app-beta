"""Gerador da base sintética com defeitos controlados e gabarito.

Documentação: ``docs/testes/base-sintetica.md``.

Uso::

    uv run --project engine python tools/synth/synth.py demo --out ./lote-demo --pages 200
    uv run --project engine python tools/synth/synth.py conformance --out conformance/fixtures/core
    uv run --project engine python tools/synth/synth.py showcase --out ./lote-demonstracao

Cada defeito inserido gera uma linha no gabarito (``gabarito.json``). O
gerador usa semente fixa: a mesma linha de comando produz os mesmos arquivos
na mesma máquina. A numeração manuscrita é simulada em ``numbering.json``,
no formato que o leitor de manuscrito produz (``docs/especificacoes/sequencing.md``).
"""

from __future__ import annotations

import argparse
import json
import os
import random
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray
from PIL import Image, ImageDraw, ImageFont

DPI = 300
FONT_DIRS = [
    *([Path(os.environ["QA_SYNTH_FONT_DIR"])] if os.environ.get("QA_SYNTH_FONT_DIR") else []),
    Path("/usr/share/fonts/truetype/dejavu"),
    Path("/usr/share/fonts/dejavu"),
]
"""Onde procurar as fontes DejaVu; ``QA_SYNTH_FONT_DIR`` vem primeiro (Windows, macOS)."""
WORDS = [
    "processo",
    "contrato",
    "cláusula",
    "partes",
    "objeto",
    "valor",
    "prazo",
    "pagamento",
    "empresa",
    "cidade",
    "estado",
    "documento",
    "certidão",
    "registro",
    "nota",
    "fiscal",
    "data",
    "assinatura",
    "testemunha",
    "juízo",
    "vara",
    "cível",
    "autos",
    "requerente",
    "requerido",
    "petição",
    "despacho",
    "decisão",
    "sentença",
    "recurso",
    "prazo",
    "dias",
    "úteis",
    "art",
    "lei",
    "decreto",
    "termo",
    "ata",
    "reunião",
    "conselho",
    "diretoria",
    "sociedade",
    "capital",
    "social",
    "sede",
    "endereço",
    "rua",
    "avenida",
    "número",
    "bairro",
    "cep",
    "telefone",
    "conforme",
    "segue",
    "abaixo",
    "acima",
    "referido",
]
STATIONS = [
    ("Kodak", "i4250", "Unidade Campo Grande, Estação 3"),
    ("Kodak", "S2085f", "Unidade Centro, Estação 1"),
]


def _font(size: int, bold: bool = False, oblique: bool = False) -> ImageFont.FreeTypeFont:
    """Fonte DejaVu; sem a variante oblíqua (pacote fonts-dejavu-core), usa a reta."""
    if bold:
        names = ["DejaVuSerif-Bold.ttf"]
    elif oblique:
        names = ["DejaVuSansMono-Oblique.ttf", "DejaVuSansMono.ttf"]
    else:
        names = ["DejaVuSerif.ttf"]
    for name in names:
        for folder in FONT_DIRS:
            if (folder / name).is_file():
                return ImageFont.truetype(str(folder / name), size)
    raise SystemExit(
        f"fonte {names[0]} não encontrada (instale fonts-dejavu-core ou defina QA_SYNTH_FONT_DIR)"
    )


@dataclass
class Page:
    """Página em construção: imagem, DPI e folha."""

    gray: NDArray[np.uint8]
    dpi: int = DPI
    folio: int | None = None


@dataclass
class Truth:
    """Gabarito: uma linha por defeito inserido."""

    items: list[dict[str, Any]] = field(default_factory=list)

    def add(self, rule: str, **where: Any) -> None:
        """Registra um defeito no gabarito."""
        self.items.append({"rule": rule, **where})


def text_page(
    rng: random.Random,
    size: tuple[int, int],
    folio: int,
    doc_pages: int,
    position: int,
    density: float = 1.0,
) -> NDArray[np.uint8]:
    """Página limpa: título, parágrafos, rodapé "Página X de Y" e "fls." no canto."""
    w, h = size
    img = Image.new("L", size, 255)
    draw = ImageDraw.Draw(img)
    margin = int(0.09 * w)
    draw.text(
        (margin, int(0.07 * h)),
        rng.choice(["CONTRATO", "CERTIDÃO", "PETIÇÃO", "ATA"])
        + " Nº "
        + str(rng.randint(100, 9999)),
        font=_font(int(h * 0.018), bold=True),
        fill=20,
    )
    body = _font(int(h * 0.0125))
    y = int(0.13 * h)
    line_h = int(h * 0.022)
    lines = int((0.78 * h) // line_h * density)
    for i in range(lines):
        if i % 9 == 8:
            y += line_h // 2
            continue
        words = [rng.choice(WORDS) for _ in range(rng.randint(9, 13))]
        draw.text((margin, y), " ".join(words), font=body, fill=rng.randint(15, 45))
        y += line_h
    draw.text(
        (w // 2 - int(0.06 * w), int(0.95 * h)),
        f"Página {position} de {doc_pages}",
        font=_font(int(h * 0.01)),
        fill=40,
    )
    draw.text(
        (int(0.80 * w), int(0.03 * h)),
        f"fls. {folio}",
        font=_font(int(h * 0.016), oblique=True),
        fill=60,
    )
    arr = np.asarray(img).astype(np.float32)
    paper = rng.uniform(236, 246)
    arr = arr / 255.0 * paper
    np_rng = np.random.default_rng(rng.randint(0, 2**31))
    arr += np_rng.normal(0, 2.5, arr.shape)
    return np.clip(arr, 0, 255).astype(np.uint8)


def stamp_page(rng: random.Random, size: tuple[int, int]) -> NDArray[np.uint8]:
    """Verso só com carimbo: um círculo com texto, levemente inclinado, sobre papel."""
    w, h = size
    stamp = Image.new("L", (int(w * 0.32), int(w * 0.32)), 255)
    draw = ImageDraw.Draw(stamp)
    s = stamp.size[0]
    draw.ellipse((4, 4, s - 4, s - 4), outline=60, width=max(3, s // 60))
    font = _font(int(s * 0.14), bold=True)
    draw.text((s * 0.13, s * 0.40), "RECEBIDO", font=font, fill=60)
    stamp = stamp.rotate(rng.uniform(-20, 20), fillcolor=255)
    page = Image.fromarray(blank_page(rng, size))
    mask = Image.fromarray((np.asarray(stamp) < 200).astype(np.uint8) * 255)
    page.paste(Image.new("L", stamp.size, 70), (int(w * 0.55), int(h * 0.62)), mask)
    return np.asarray(page)


def blank_page(rng: random.Random, size: tuple[int, int]) -> NDArray[np.uint8]:
    """Página em branco com ruído de papel."""
    np_rng = np.random.default_rng(rng.randint(0, 2**31))
    arr = np_rng.normal(rng.uniform(236, 246), 2.5, (size[1], size[0]))
    return np.clip(arr, 0, 255).astype(np.uint8)


# Defeitos -----------------------------------------------------------------


def d_blur(p: Page, rng: random.Random) -> dict[str, Any]:
    """Desfoque gaussiano."""
    sigma = rng.uniform(2.5, 4.0)
    p.gray = cv2.GaussianBlur(p.gray, (0, 0), sigma)
    return {"sigma": round(sigma, 2)}


def d_skew(p: Page, rng: random.Random, angle: float | None = None) -> dict[str, Any]:
    """Inclinação (positivo = horário)."""
    a = angle if angle is not None else rng.choice([-1, 1]) * rng.uniform(1.0, 5.0)
    h, w = p.gray.shape
    # Positivo = sentido horário (contrato). No OpenCV, ângulo positivo é anti-horário.
    m = cv2.getRotationMatrix2D((w / 2, h / 2), -a, 1.0)
    p.gray = cv2.warpAffine(p.gray, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=242)
    return {"angle_deg": round(a, 2)}


def d_borders(p: Page, rng: random.Random) -> dict[str, Any]:
    """Faixa preta numa margem."""
    h, w = p.gray.shape
    frac = rng.uniform(0.02, 0.05)
    side = rng.choice(["left", "right", "top"])
    band = int(frac * (w if side != "top" else h))
    if side == "left":
        p.gray[:, :band] = 12
    elif side == "right":
        p.gray[:, w - band :] = 12
    else:
        p.gray[:band, :] = 12
    return {"side": side, "fraction": round(frac, 3)}


def d_dark(p: Page, rng: random.Random) -> dict[str, Any]:
    """Página escura."""
    f = rng.uniform(0.45, 0.6)
    p.gray = (p.gray.astype(np.float32) * f).astype(np.uint8)
    return {"factor": round(f, 2)}


def d_faded(p: Page, rng: random.Random) -> dict[str, Any]:
    """Tinta desbotada (sem contraste)."""
    f = rng.uniform(0.2, 0.35)
    p.gray = (255 - (255 - p.gray.astype(np.float32)) * f).astype(np.uint8)
    return {"ink_factor": round(f, 2)}


def d_lowres(p: Page, rng: random.Random) -> dict[str, Any]:
    """Resolução reduzida (150 ou 200 dpi)."""
    dpi = rng.choice([150, 200])
    h, w = p.gray.shape
    p.gray = cv2.resize(p.gray, (w * dpi // DPI, h * dpi // DPI), interpolation=cv2.INTER_AREA)
    p.dpi = dpi
    return {"dpi": dpi}


def d_rotate(p: Page, rng: random.Random, angle: int | None = None) -> dict[str, Any]:
    """Página digitalizada de lado ou de cabeça para baixo (giro horário de 90, 180 ou 270)."""
    angle = angle if angle is not None else rng.choice([90, 180, 270])
    turns = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}
    p.gray = np.ascontiguousarray(cv2.rotate(p.gray, turns[angle]))
    return {"angle_deg": angle}


PAGE_DEFECTS = {
    "orientation": d_rotate,
    "blur": d_blur,
    "skew": d_skew,
    "black_borders": d_borders,
    "exposure": d_dark,
    "exposure_faded": d_faded,
    "low_resolution": d_lowres,
}


# Gravação -----------------------------------------------------------------


def save_tiff(path: Path, page: Page, station: tuple[str, str, str], day: int) -> None:
    """Grava TIFF com tags de captura (equipamento, data, operador)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    make, model, _ = station
    Image.fromarray(page.gray).save(
        path,
        compression="tiff_deflate",
        dpi=(page.dpi, page.dpi),
        tiffinfo={
            271: make,
            272: model,
            305: "qa-synth 0.1",
            306: f"2026:11:{day:02d} 10:{len(path.name) % 60:02d}:00",
            315: "operador01",
        },
    )


def marks_for(
    folio: int | None, rng: random.Random, misread: bool = False, struck_old: int | None = None
) -> list[dict[str, Any]]:
    """Marcas de numeração simuladas, no formato do leitor de manuscrito."""
    if folio is None:
        return []
    if misread:
        wrong = folio + rng.choice([4, 5, 6, 50])
        marks = [
            {
                "struck": False,
                "readings": [
                    {"text": str(wrong), "confidence": round(rng.uniform(0.55, 0.7), 3)},
                    {"text": str(folio), "confidence": round(rng.uniform(0.1, 0.3), 3)},
                ],
            }
        ]
    else:
        marks = [
            {
                "struck": False,
                "readings": [{"text": str(folio), "confidence": round(rng.uniform(0.88, 0.99), 3)}],
            }
        ]
    if struck_old is not None:
        marks.append({"struck": True, "readings": [{"text": str(struck_old), "confidence": 0.9}]})
    return marks


def build(out: Path, plan: list[list[dict[str, Any]]], seed: int, size: tuple[int, int]) -> None:
    """Gera o lote a partir de um plano: lista de documentos, cada um com páginas."""
    rng = random.Random(seed)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    truth = Truth()
    numbering: dict[str, Any] = {}
    manifest_rows: list[tuple[str, int]] = []
    for d, doc in enumerate(plan, start=1):
        box = f"CX{(d - 1) // 10 + 1:03d}"
        name = f"{box}/DOC{d:04d}"
        station = STATIONS[(d - 1) // 10 % len(STATIONS)]
        pages: list[tuple[Page, dict[str, Any]]] = []
        for i, spec in enumerate(doc, start=1):
            folio = spec.get("folio", i)
            if spec.get("kind") == "blank":
                page = Page(blank_page(rng, size), folio=None)
            elif spec.get("kind") == "stamp":
                page = Page(stamp_page(rng, size), folio=None)
            else:
                page = Page(
                    text_page(rng, size, folio, len(doc), i, spec.get("density", 1.0)), folio=folio
                )
            pages.append((page, spec))
        # Duplicatas: cópia levemente desfocada e deslocada de uma página anterior.
        for idx, (_, spec) in enumerate(pages):
            if "duplicate_of" in spec:
                src = pages[spec["duplicate_of"]][0]
                m = np.float32([[1, 0, 2], [0, 1, 3]])
                g = cv2.warpAffine(src.gray, m, (size[0], size[1]), borderValue=242)
                pages[idx] = (Page(cv2.GaussianBlur(g, (0, 0), 0.6), folio=src.folio), spec)
        written = 0
        for page, spec in pages:
            if spec.get("drop"):
                truth.add("missing_page", document=name, folio=page.folio)
                continue
            written += 1
            rel = f"{name}/{written:04d}.tif"
            params = {}
            defect = spec.get("defect")
            if defect:
                fn = PAGE_DEFECTS[defect]
                params = fn(page, rng, **spec.get("defect_args", {}))
                truth.add(defect.split("_faded")[0], file=rel, page_in_file=0, params=params)
            if spec.get("kind") in {"blank", "stamp"}:
                # Só carimbo: "quase branca", nunca removida (blank_page.md).
                truth.add("blank_page", file=rel, page_in_file=0)
            if "duplicate_of" in spec:
                src_rel = f"{name}/{spec['duplicate_of'] + 1:04d}.tif"
                truth.add("duplicate_page", file=rel, page_in_file=0, alternatives=[src_rel])
            save_tiff(out / rel, page, station, 1 + d % 28)
            corrupt = spec.get("corrupt")
            if corrupt == "truncate":
                data = (out / rel).read_bytes()
                (out / rel).write_bytes(data[: len(data) // 3])
            elif corrupt == "empty":
                (out / rel).write_bytes(b"")
            if corrupt:
                truth.add("corrupted_file", file=rel, page_in_file=0)
            misread = bool(spec.get("misread"))
            if misread:
                truth.add("numbering_review", file=rel, page_in_file=0)
            numbering[f"{rel}#0"] = marks_for(
                page.folio, rng, misread=misread, struck_old=spec.get("struck_old")
            )
        if any("swap_with" in s for s in doc):
            truth.add("out_of_order", document=name)
        manifest_rows.append((name, written))
        _apply_swaps(out, name, doc, numbering)
    (out / "numbering.json").write_text(
        json.dumps({"pages": numbering}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    (out / "gabarito.json").write_text(
        json.dumps(
            {"seed": seed, "pages": sum(n for _, n in manifest_rows), "defects": truth.items},
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )


def _apply_swaps(
    out: Path, name: str, doc: list[dict[str, Any]], numbering: dict[str, Any]
) -> None:
    """Troca os arquivos de duas páginas (numeração continua presa à imagem)."""
    for i, spec in enumerate(doc, start=1):
        j = spec.get("swap_with")
        if j is None or j < i:
            continue
        a, b = out / f"{name}/{i:04d}.tif", out / f"{name}/{j:04d}.tif"
        tmp = a.with_suffix(".tmp")
        a.rename(tmp)
        b.rename(a)
        tmp.rename(b)
        ka, kb = f"{name}/{i:04d}.tif#0", f"{name}/{j:04d}.tif#0"
        numbering[ka], numbering[kb] = numbering[kb], numbering[ka]


def demo_plan(
    pages: int, seed: int, defect_rate: float, doc_size: int
) -> list[list[dict[str, Any]]]:
    """Plano da demonstração: cerca de ``defect_rate`` das páginas com defeito."""
    rng = random.Random(seed + 1)
    defects = list(PAGE_DEFECTS)
    plan: list[list[dict[str, Any]]] = []
    remaining = pages
    while remaining > 0:
        n = min(doc_size, remaining)
        doc: list[dict[str, Any]] = [{} for _ in range(n)]
        for spec in doc:
            if rng.random() < defect_rate * 0.75:
                spec["defect"] = rng.choice(defects)
        r = rng.random()
        if n >= 5 and r < 0.12:
            doc[rng.randrange(1, n - 1)] = {"drop": True}
        elif n >= 5 and r < 0.22:
            i = rng.randrange(1, n - 2)
            if not doc[i] and not doc[i + 1]:
                doc[i]["swap_with"], doc[i + 1]["swap_with"] = i + 2, i + 1
        elif n >= 5 and r < 0.30:
            doc[n - 1] = {"duplicate_of": rng.randrange(0, n - 1)}
        elif r < 0.36:
            doc[rng.randrange(0, n)] = {"kind": "blank"}
        elif r < 0.40:
            doc[rng.randrange(0, n)]["misread"] = True
        elif r < 0.43:
            doc[rng.randrange(0, n)] = {"corrupt": "truncate"}
        plan.append(doc)
        remaining -= n
    return plan


def conformance_plan() -> list[list[dict[str, Any]]]:
    """Lote fixo da suíte de conformidade: cada regra dispara ao menos uma vez."""
    clean: dict[str, Any] = {}
    return [
        [
            dict(clean),
            {"defect": "blur"},
            dict(clean),
            {"defect": "skew", "defect_args": {"angle": 2.0}},
            dict(clean),
        ],
        [
            dict(clean),
            {"defect": "skew", "defect_args": {"angle": -4.0}},
            {"defect": "black_borders"},
            dict(clean),
            {"kind": "blank"},
        ],
        [
            dict(clean),
            {"defect": "exposure"},
            {"defect": "exposure_faded"},
            dict(clean),
            {"defect": "low_resolution"},
        ],
        [dict(clean), dict(clean), {"drop": True}, dict(clean), dict(clean)],
        [dict(clean), {"swap_with": 3}, {"swap_with": 2}, dict(clean), {"duplicate_of": 0}],
        [
            dict(clean),
            {"misread": True},
            dict(clean),
            {"corrupt": "truncate"},
            {"corrupt": "empty"},
        ],
        [
            dict(clean),
            {"defect": "orientation", "defect_args": {"angle": 90}},
            {"defect": "orientation", "defect_args": {"angle": 180}},
            {"defect": "orientation", "defect_args": {"angle": 270}},
            {"density": 0.12},
            {"kind": "stamp"},
        ],
    ]


def showcase_plan() -> list[list[dict[str, Any]]]:
    """Lote da demonstração (ADR-0010): os quatro casos em foco no mesmo documento.

    CX001/DOC0001: página torta, folha 4 faltando, página sem nitidez e página em branco.
    CX001/DOC0002: duas folhas trocadas (ordem pela numeração) e uma página torta.
    CX001/DOC0003 a CX002/DOC0012: documentos limpos de 2 páginas. Com poucos documentos
    verdes, a amostragem de 5% (arredondada para cima) sortearia todos; dez deixam a
    métrica "páginas que dispensam revisão" representativa.
    """
    clean: dict[str, Any] = {}
    return [
        [
            dict(clean),
            {"defect": "skew", "defect_args": {"angle": 2.5}},
            dict(clean),
            {"drop": True},
            dict(clean),
            {"defect": "blur"},
            {"kind": "blank"},
            dict(clean),
        ],
        [
            dict(clean),
            dict(clean),
            {"swap_with": 4},
            {"swap_with": 3},
            dict(clean),
            {"defect": "skew", "defect_args": {"angle": -1.8}},
        ],
        *([dict(clean), dict(clean)] for _ in range(10)),
    ]


def selftest_plan() -> list[list[dict[str, Any]]]:
    """Lote pequeno do teste de fumaça do executável: um defeito de cada tipo robusto.

    CX001/DOC0001: página torta, folha 3 faltando e página em branco.
    CX001/DOC0002: página sem nitidez.
    """
    clean: dict[str, Any] = {}
    return [
        [
            dict(clean),
            {"defect": "skew", "defect_args": {"angle": 3.0}},
            {"drop": True},
            dict(clean),
            {"kind": "blank"},
        ],
        [dict(clean), {"defect": "blur"}, dict(clean)],
    ]


def main() -> None:
    """Linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["demo", "conformance", "showcase", "selftest"])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--pages", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20261105)
    parser.add_argument("--defect-rate", type=float, default=0.25)
    parser.add_argument("--doc-size", type=int, default=10)
    parser.add_argument("--a5", action="store_true", help="páginas A5 (arquivos menores)")
    args = parser.parse_args()
    a5 = args.a5 or args.mode in {"conformance", "showcase"}
    size = (1748, 2480) if a5 else (2480, 3508)
    if args.mode == "selftest":
        size = (1240, 1748)  # A6 a 300 dpi: o lote vai dentro do pacote
        plan = selftest_plan()
    elif args.mode == "conformance":
        plan = conformance_plan()
    elif args.mode == "showcase":
        plan = showcase_plan()
    else:
        plan = demo_plan(args.pages, args.seed, args.defect_rate, args.doc_size)
    build(args.out, plan, args.seed, size)
    print(f"lote gerado em {args.out}")


if __name__ == "__main__":
    main()
