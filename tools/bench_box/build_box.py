"""Gera a caixa de regressão: 1.000 páginas em processos de tamanhos desiguais.

As folhas são páginas reais do RVL-CDIP (``fetch_pool.py`` baixa as listadas em
``folhas-limpas.txt``), ampliadas para 300 dpi; só as 30 folhas em branco são sintéticas.
Os problemas são sorteados com semente fixa, e o gabarito descreve o que foi inserido.
Ver ``docs/testes/caixa-de-regressao.md``.

Uso::

    python3 tools/bench_box/build_box.py <pasta_das_folhas> \
        tools/bench_box/folhas-limpas.txt <saida> 2026

Saída: ``<saida>/caixa teste/`` (com ``manifest.csv``), ``<saida>/gabarito_caixa_teste.csv``
e ``<saida>/paginas_perdidas.csv``. A ordem das chamadas ao gerador aleatório faz parte do
formato: mudá-la muda a caixa inteira.
"""

from __future__ import annotations

import csv
import os
import random
import sys
from collections.abc import Callable, Iterator
from typing import Any

import numpy as np
from PIL import Image, ImageFilter, ImageOps

TOTAL = 1000
SCALE = 3.3
"""Ampliação: cerca de 91 dpi do RVL-CDIP para 300 dpi (folha carta)."""
DPI = 300
BLANK_SIZE = (2558, 3300)

SINGLE = (
    ["rotacao"] * 60
    + ["inclinacao"] * 50
    + ["desfoque"] * 30
    + ["exposicao_escura"] * 15
    + ["exposicao_clara"] * 15
    + ["borda_preta"] * 30
    + ["baixa_resolucao"] * 25
)
COMBOS = (
    [("rotacao", "inclinacao")] * 5
    + [("baixa_resolucao", "desfoque")] * 4
    + [("exposicao_escura", "borda_preta")] * 3
    + [("rotacao", "borda_preta")] * 3
)
SPECIAL = ["branca"] * 20 + ["branca_verso"] * 10 + ["duplicata"] * 25 + ["corrompido"] * 8

Slot = tuple[str, ...]


class Box:
    """Estado do gerador: sementes, folhas de origem e saída."""

    def __init__(self, pool_dir: str, clean: list[str], out_dir: str, seed: int) -> None:
        self.rng = random.Random(seed)
        self.nrng = np.random.default_rng(seed)
        self.pool_dir = pool_dir
        self.out_dir = out_dir
        self.box = os.path.join(out_dir, "caixa teste")
        self.rng.shuffle(clean)
        self.clean: Iterator[str] = iter(clean)
        self.ops: dict[str, Callable[[Image.Image, dict[str, Any]], Image.Image]] = {
            "rotacao": self.op_rotacao,
            "inclinacao": self.op_inclinacao,
            "desfoque": self.op_desfoque,
            "exposicao_escura": self.op_exposicao_escura,
            "exposicao_clara": self.op_exposicao_clara,
            "borda_preta": self.op_borda_preta,
        }

    # Plano -------------------------------------------------------------------------

    def sizes(self) -> list[int]:
        """Tamanhos desiguais dos processos, somando ``TOTAL``."""
        n_proc = self.rng.randint(10, 14)
        while True:
            weights = [self.rng.paretovariate(1.2) for _ in range(n_proc)]
            sizes = [max(25, round(TOTAL * x / sum(weights))) for x in weights]
            sizes[sizes.index(max(sizes))] += TOTAL - sum(sizes)
            if min(sizes) >= 25 and max(sizes) <= 220 and len(set(sizes)) == n_proc:
                return sizes

    def plan(self, sizes: list[int]) -> list[list[Slot]]:
        """Problemas sorteados nas páginas; todo processo com pelo menos 4 tipos."""
        for _ in range(500):
            slots: list[Slot] = [("ok",)] * TOTAL
            items: list[Slot] = [(s,) for s in SINGLE] + list(COMBOS) + [(s,) for s in SPECIAL]
            for p, it in zip(self.rng.sample(range(TOTAL), len(items)), items, strict=True):
                slots[p] = it
            plan, k = [], 0
            for s in sizes:
                plan.append(slots[k : k + s])
                k += s
            if all(_dup_after_clean(p) for p in plan) and all(_kinds(p) >= 4 for p in plan):
                return plan
        raise SystemExit("não achei plano")

    # Imagens -----------------------------------------------------------------------

    def load_real(self, name: str) -> Image.Image:
        """Folha de origem ampliada para 300 dpi."""
        im = Image.open(os.path.join(self.pool_dir, name)).convert("L")
        size = (round(im.width * SCALE), round(im.height * SCALE))
        return im.resize(size, Image.Resampling.LANCZOS)

    def synth_blank(self, w: int, h: int, verso_src: Image.Image | None = None) -> Image.Image:
        """Folha em branco: papel, gradiente, ruído, poeira e, opcional, transparência."""
        rng = self.rng
        paper = rng.uniform(228, 248)
        yy, xx = np.mgrid[0:h, 0:w]
        grad = (xx / w - 0.5) * rng.uniform(-6, 6) + (yy / h - 0.5) * rng.uniform(-6, 6)
        a = paper + grad + self.nrng.normal(0, rng.uniform(1.5, 3.0), (h, w))
        if verso_src is not None:  # página real espelhada, contraste baixo
            v = np.asarray(
                verso_src.resize((w, h)).transpose(Image.Transpose.FLIP_LEFT_RIGHT), dtype=float
            )
            a -= (255 - v) / 255 * rng.uniform(10, 18)
        for _ in range(rng.randint(0, 6)):  # poeira
            cy, cx, r = rng.randrange(h), rng.randrange(w), rng.randint(1, 3)
            a[max(0, cy - r) : cy + r, max(0, cx - r) : cx + r] -= rng.uniform(40, 90)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))

    def op_rotacao(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Giro de 90, 180 ou 270 graus no sentido horário."""
        ang = self.rng.choice([90, 180, 270])
        p["giro_horario_graus"] = ang
        p["correcao"] = f"girar {(360 - ang) % 360}° no sentido horário"
        return im.rotate(-ang, expand=True)

    def op_inclinacao(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Inclinação de 1,5° a 6°, para um dos lados."""
        deg = round(self.rng.uniform(1.5, 6.0) * self.rng.choice([-1, 1]), 1)
        p["inclinacao_graus"] = deg
        return im.rotate(
            deg, expand=True, resample=Image.Resampling.BICUBIC, fillcolor=paper_level(im)
        )

    def op_desfoque(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Desfoque gaussiano de raio 3 a 5 px a 300 dpi."""
        r = round(self.rng.uniform(3.0, 5.0), 1)
        p["desfoque_raio_px_300dpi"] = r
        return im.filter(ImageFilter.GaussianBlur(r))

    def op_exposicao_escura(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Página inteira escurecida."""
        f = round(self.rng.uniform(0.50, 0.62), 2)
        p["exposicao_fator"] = f
        return im.point(lambda v: int(v * f))

    def op_exposicao_clara(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Tinta desbotada: o preto vira cinza."""
        lift = self.rng.randint(120, 160)
        p["exposicao_tinta_minima"] = lift
        return im.point(lambda v: int(lift + v * (255 - lift) / 255))

    def op_borda_preta(self, im: Image.Image, p: dict[str, Any]) -> Image.Image:
        """Faixa escura de 3% a 8% em um ou dois lados."""
        sides = self.rng.sample(["esquerda", "direita", "topo", "base"], self.rng.randint(1, 2))
        frac = round(self.rng.uniform(0.03, 0.08), 3)
        p["borda_lados"] = "+".join(sides)
        p["borda_fracao"] = frac
        a = np.asarray(im).copy()
        h, w = a.shape
        bw, bh = int(w * frac), int(h * frac)
        for s in sides:
            if s == "esquerda":
                a[:, :bw] = self.dark(a[:, :bw].shape)
            if s == "direita":
                a[:, w - bw :] = self.dark(a[:, w - bw :].shape)
            if s == "topo":
                a[:bh] = self.dark(a[:bh].shape)
            if s == "base":
                a[h - bh :] = self.dark(a[h - bh :].shape)
        return Image.fromarray(a)

    def dark(self, shape: tuple[int, ...]) -> Any:
        """Ruído escuro de fundo do digitalizador."""
        return self.nrng.integers(5, 35, shape, dtype=np.uint8)

    # Montagem ----------------------------------------------------------------------

    def build(self) -> list[int]:
        """Grava a caixa, o ``manifest.csv`` e os gabaritos; devolve os tamanhos."""
        os.makedirs(self.box, exist_ok=True)
        sizes = self.sizes()
        plan = self.plan(sizes)
        gab: list[dict[str, Any]] = []
        manifest: list[list[Any]] = []
        used_dupes: set[str] = set()  # nome do arquivo, na caixa inteira (faz parte do formato)
        for pi, slots in enumerate(plan, start=1):
            pdir = os.path.join(self.box, f"processo {pi}")
            os.makedirs(pdir, exist_ok=True)
            clean_pages: list[tuple[int, str, str]] = []
            for i, slot in enumerate(slots, start=1):
                gab.append(self.page(pi, pdir, i, slot, clean_pages, used_dupes))
            manifest.append([f"processo {pi}", len(slots)])
        self.write_tables(gab, manifest)
        return sizes

    def page(
        self,
        pi: int,
        pdir: str,
        i: int,
        slot: Slot,
        clean_pages: list[tuple[int, str, str]],
        used_dupes: set[str],
    ) -> dict[str, Any]:
        """Grava uma página e devolve a linha do gabarito."""
        fname = f"{i:04d}.png"
        path = os.path.join(pdir, fname)
        p: dict[str, Any] = {}
        dpi, origem, tipo = DPI, "", "real"
        kinds = [k for k in slot if k != "ok"]
        if kinds in (["branca"], ["branca_verso"]):
            tipo = "branca_sintetica"
            verso = None
            if kinds == ["branca_verso"]:
                origem = next(self.clean)
                verso = Image.open(os.path.join(self.pool_dir, origem)).convert("L")
                p["verso_de"] = origem
            im = self.synth_blank(*BLANK_SIZE, verso)
            p["correcao"] = "remover (página em branco)"
        elif kinds == ["duplicata"]:
            tipo = "duplicata"
            cands = [c for c in clean_pages if c[1] not in used_dupes]
            _, src_name, src_file = self.rng.choice(cands[-5:]) if cands else clean_pages[-1]
            used_dupes.add(src_name)
            with Image.open(os.path.join(pdir, src_name)) as src:
                im = src.copy()
            if self.rng.random() < 0.5:  # redigitalização: deslocamento e ruído
                dx, dy = self.rng.randint(-12, 12), self.rng.randint(-12, 12)
                a = np.asarray(im.convert("L"), dtype=float)
                a = np.roll(np.roll(a, dy, 0), dx, 1) + self.nrng.normal(0, 2, a.shape)
                im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
                p["variacao"] = f"rescan dx={dx} dy={dy}"
            else:
                p["variacao"] = "cópia exata"
            origem = src_file
            p["duplicata_de"] = src_name
            p["correcao"] = "remover duplicata"
        elif kinds == ["corrompido"]:
            origem = next(self.clean)
            finish(self.load_real(origem)).save(path, dpi=(DPI, DPI), optimize=True)
            size = os.path.getsize(path)
            if self.rng.random() < 0.25:
                open(path, "wb").close()
                p["corrupcao"] = "arquivo de 0 byte"
            else:
                cut = self.rng.uniform(0.25, 0.6)
                with open(path, "r+b") as fh:
                    fh.truncate(int(size * cut))
                p["corrupcao"] = f"truncado em {cut:.0%}"
            p["correcao"] = "redigitalizar"
            return _row(pi, fname, "corrompido", origem, "corrompido", p)
        else:
            origem = next(self.clean)
            im = self.load_real(origem)
            for k in kinds:
                if k == "baixa_resolucao":
                    dpi = self.rng.choice([150, 200])
                    p["dpi"] = dpi
                    size = (round(im.width * dpi / DPI), round(im.height * dpi / DPI))
                    im = im.resize(size, Image.Resampling.LANCZOS)
            for k in kinds:
                if k != "baixa_resolucao":
                    im = self.ops[k](im, p)
            if not kinds:
                clean_pages.append((i, fname, origem))
        finish(im).save(path, dpi=(dpi, dpi), optimize=True)
        return _row(pi, fname, tipo, origem, "+".join(kinds) if kinds else "nenhum", p)

    def write_tables(self, gab: list[dict[str, Any]], manifest: list[list[Any]]) -> None:
        """``manifest.csv`` (3 processos declaram folhas a mais) e os dois gabaritos."""
        for j in self.rng.sample(range(len(manifest)), 3):
            extra = self.rng.randint(1, 3)
            manifest[j].append(extra)
            manifest[j][1] += extra
        with open(os.path.join(self.box, "manifest.csv"), "w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["document", "pages"])
            for row in manifest:
                w.writerow(row[:2])
        fields = ["processo", "arquivo", "tipo_folha", "origem", "problemas", "detalhes"]
        path = os.path.join(self.out_dir, "gabarito_caixa_teste.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            dw = csv.DictWriter(fh, fieldnames=fields)
            dw.writeheader()
            dw.writerows(gab)
        path = os.path.join(self.out_dir, "paginas_perdidas.csv")
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                ["processo", "paginas_presentes", "paginas_declaradas_no_manifest", "faltando"]
            )
            for row in manifest:
                if len(row) == 3:
                    w.writerow([row[0], row[1] - row[2], row[1], row[2]])


def paper_level(im: Image.Image) -> int:
    """Brilho do papel junto às bordas (percentil 75)."""
    a = np.asarray(im)
    border = np.concatenate(
        [a[:20].ravel(), a[-20:].ravel(), a[:, :20].ravel(), a[:, -20:].ravel()]
    )
    return int(np.percentile(border, 75))


def finish(im: Image.Image) -> Image.Image:
    """16 níveis de cinza: arquivo menor, sem perder a forma do conteúdo."""
    return ImageOps.posterize(im, 4)


def _row(
    pi: int, fname: str, tipo: str, origem: str, problemas: str, p: dict[str, Any]
) -> dict[str, Any]:
    return {
        "processo": pi,
        "arquivo": fname,
        "tipo_folha": tipo,
        "origem": origem,
        "problemas": problemas,
        "detalhes": "; ".join(f"{k}={v}" for k, v in p.items()),
    }


def _dup_after_clean(slots: list[Slot]) -> bool:
    """Toda duplicata tem uma página limpa antes dela no processo."""
    seen_ok = False
    for sl in slots:
        if sl == ("ok",):
            seen_ok = True
        if sl == ("duplicata",) and not seen_ok:
            return False
    return True


def _kinds(slots: list[Slot]) -> int:
    kinds: set[str] = set()
    for sl in slots:
        kinds |= set(sl)
    kinds.discard("ok")
    return len(kinds)


def main() -> None:
    """Ponto de entrada."""
    if len(sys.argv) != 5:
        sys.exit(__doc__)
    pool_dir, clean_list, out_dir, seed = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
    with open(clean_list, encoding="utf-8") as fh:
        clean = [line.strip() for line in fh if line.strip()]
    sizes = Box(pool_dir, clean, out_dir, seed).build()
    print("processos", len(sizes), "tamanhos", sizes, "total", sum(sizes))


if __name__ == "__main__":
    main()
