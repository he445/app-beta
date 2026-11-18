"""Bench dos reconhecedores de numeração: acerto, acerto entre as três leituras, ambíguo e tempo.

Roda cada reconhecedor numa pasta de recortes rotulados (``labels.json``: arquivo,
texto, riscado). Antes do beta, com recortes sintéticos (``tools/synth/numbering.py
recortes``); durante o beta, com os recortes que os garantidores confirmaram
(``qa feedback export``). Vence quem acerta mais entre as três leituras dentro do
orçamento de tempo.

Com ``--reader``, mede o que o resolvedor de sequência recebe: a etapa 4 do leitor
(formato de folha, melhor leitura com confiança mínima, leituras secundárias e
alternativas da tabela de trocas do perfil). ``--top`` muda quantas leituras contam
(padrão 3). ``--reliability`` mede a confiabilidade da confiança: acerto da primeira
leitura por faixa de 0,05 e erro acima de cada limiar (para escolher ``high_confidence``).

Uso::

    uv run --project engine python tools/bench_numbering.py recortes --models models
    uv run --project engine python tools/bench_numbering.py recortes --models models --json
    uv run --project engine python tools/bench_numbering.py recortes --models models
        --reader --profile profiles/sos-piloto.yaml --top 5
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray
from PIL import Image

Reading = tuple[str, float]
Recognize = Callable[[NDArray[np.uint8]], Sequence[Reading]]


def canonical(text: str) -> str | None:
    """Forma canônica de um número de folha (``fls. 12`` → ``12``); ``None`` se não for."""
    from qa_engine.domain.sequencing import parse_folio

    folio = parse_folio(text)
    return str(folio) if folio is not None else None


@dataclass(frozen=True, slots=True)
class BenchResult:
    """Métricas de um reconhecedor."""

    name: str
    n: int
    exact: float
    top3: float
    ambiguous: float
    ms_per_crop: float
    exact_struck: float | None
    exact_clean: float | None

    def json(self) -> dict[str, Any]:
        """Uma linha do relatório."""
        return {
            "name": self.name,
            "n": self.n,
            "exact": round(self.exact, 4),
            "top3": round(self.top3, 4),
            "ambiguous": round(self.ambiguous, 4),
            "ms_per_crop": round(self.ms_per_crop, 1),
            "exact_struck": None if self.exact_struck is None else round(self.exact_struck, 4),
            "exact_clean": None if self.exact_clean is None else round(self.exact_clean, 4),
        }


def load_crops(folder: Path) -> list[tuple[NDArray[np.uint8], Mapping[str, Any]]]:
    """Recortes em cinza e seus rótulos."""
    labels = json.loads((folder / "labels.json").read_text("utf-8"))
    return [(np.asarray(Image.open(folder / item["file"]).convert("L")), item) for item in labels]


def bench(
    name: str,
    recognize: Recognize,
    crops: Sequence[tuple[NDArray[np.uint8], Mapping[str, Any]]],
    min_confidence: float = 0.5,
    top: int = 3,
) -> BenchResult:
    """Mede um reconhecedor nos recortes.

    Acerto exato: a primeira leitura, na forma canônica, é o rótulo. Acerto entre as
    três: alguma das ``top`` primeiras é. Ambíguo: nenhuma leitura forma número de folha com
    confiança de pelo menos ``min_confidence`` (vai para o garantidor).
    """
    hits: list[bool] = []
    hits3: list[bool] = []
    ambiguous: list[bool] = []
    struck_hits: list[bool] = []
    clean_hits: list[bool] = []
    times: list[float] = []
    for gray, label in crops:
        want = canonical(str(label["text"]))
        started = time.perf_counter()
        readings = list(recognize(gray))[:top]
        times.append(time.perf_counter() - started)
        got = [(canonical(text), conf) for text, conf in readings]
        exact = bool(got) and got[0][0] == want
        hits.append(exact)
        hits3.append(any(text == want for text, _ in got))
        ambiguous.append(not any(text is not None and conf >= min_confidence for text, conf in got))
        (struck_hits if label.get("struck") else clean_hits).append(exact)

    def rate(values: Sequence[bool]) -> float:
        return sum(values) / len(values) if values else 0.0

    return BenchResult(
        name=name,
        n=len(crops),
        exact=rate(hits),
        top3=rate(hits3),
        ambiguous=rate(ambiguous),
        ms_per_crop=1000 * statistics.mean(times) if times else 0.0,
        exact_struck=rate(struck_hits) if struck_hits else None,
        exact_clean=rate(clean_hits) if clean_hits else None,
    )


THRESHOLDS = (0.5, 0.7, 0.85, 0.9, 0.95, 0.97, 0.98, 0.99)


def reliability(
    recognize: Recognize, crops: Sequence[tuple[NDArray[np.uint8], Mapping[str, Any]]]
) -> str:
    """Acerto da primeira leitura com formato de folha por faixa de confiança de 0,05.

    Também o erro acima de cada limiar, com a fração das leituras que ficam acima, e o
    erro de calibração esperado (ECE): média ponderada de |acerto − confiança média|.
    """
    points: list[tuple[float, bool]] = []
    for gray, label in crops:
        want = canonical(str(label["text"]))
        got = [(canonical(t), c) for t, c in recognize(gray)]
        got = [(t, c) for t, c in got if t is not None]
        if got:
            points.append((got[0][1], got[0][0] == want))
    if not points:
        return "nenhuma leitura com formato de folha"
    lines = ["| Faixa | n | Acerto | Confiança média |", "| --- | --- | --- | --- |"]
    ece = 0.0
    for b in range(20):
        lo, hi = b / 20, (b + 1) / 20
        group = [(c, ok) for c, ok in points if lo <= c < hi or (b == 19 and c >= 1.0)]
        if not group:
            continue
        acc = sum(ok for _, ok in group) / len(group)
        mean = sum(c for c, _ in group) / len(group)
        ece += len(group) / len(points) * abs(acc - mean)
        lines.append(f"| {lo:.2f}–{hi:.2f} | {len(group)} | {acc:.1%} | {mean:.3f} |")
    lines += ["", "| Limiar | Acima | Erro acima |", "| --- | --- | --- |"]
    for t in THRESHOLDS:
        above = [ok for c, ok in points if c >= t]
        if above:
            wrong = len(above) - sum(above)
            lines.append(
                f"| {t} | {len(above)} ({len(above) / len(points):.1%}) | "
                f"{wrong / len(above):.2%} ({wrong}) |"
            )
    lines += ["", f"ECE: {ece:.3f} ({len(points)} leituras)"]
    return "\n".join(lines)


def reader_stage(profile: Path | None) -> Callable[[Sequence[Reading]], Sequence[Reading]]:
    """Etapa 4 do leitor com a tabela de trocas do perfil (ou a padrão)."""
    from qa_engine.application.numbering_image import DEFAULT_CONFUSIONS, candidate_readings
    from qa_engine.application.profile import load_profile

    table = load_profile(profile).numbering_reader.confusions if profile else ()
    confusions = table or DEFAULT_CONFUSIONS

    def stage(raw: Sequence[Reading]) -> Sequence[Reading]:
        return [(r.text, r.confidence) for r in candidate_readings(raw, confusions)]

    return stage


def table(results: Sequence[BenchResult]) -> str:
    """Tabela em texto: melhor acerto entre as três leituras, depois exato, depois tempo."""
    lines = [
        f"{'reconhecedor':24} {'n':>5} {'exato':>7} {'top-3':>7} {'ambíguo':>8} {'ms':>7} "
        f"{'exato riscado':>14} {'exato limpo':>12}"
    ]
    for r in sorted(results, key=lambda r: (-r.top3, -r.exact, r.ms_per_crop)):
        struck = "—" if r.exact_struck is None else f"{r.exact_struck:.1%}"
        clean = "—" if r.exact_clean is None else f"{r.exact_clean:.1%}"
        lines.append(
            f"{r.name:24} {r.n:>5} {r.exact:>7.1%} {r.top3:>7.1%} {r.ambiguous:>8.1%} "
            f"{r.ms_per_crop:>7.1f} {struck:>14} {clean:>12}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("crops", type=Path, help="pasta com labels.json e os recortes")
    parser.add_argument("--models", type=Path, required=True, help="pasta dos modelos")
    parser.add_argument("--only", action="append", default=[], help="só este reconhecedor")
    parser.add_argument(
        "--reader", action="store_true", help="mede as leituras da etapa 4 do leitor"
    )
    parser.add_argument("--profile", type=Path, help="perfil com a tabela de trocas (--reader)")
    parser.add_argument("--top", type=int, default=3, help="leituras que contam (padrão 3)")
    parser.add_argument("--reliability", action="store_true", help="acerto por faixa de confiança")
    parser.add_argument("--json", action="store_true", help="saída em JSON")
    args = parser.parse_args(argv)
    from qa_engine.adapters.text_recognition import recognizers

    crops = load_crops(args.crops)
    stage = reader_stage(args.profile) if args.reader else None
    results = []
    for name, recognizer in recognizers(args.models).items():
        if args.only and name not in args.only:
            continue

        def recognize(g: NDArray[np.uint8], r: Any = recognizer) -> Sequence[Reading]:
            raw = [(x.text, x.confidence) for x in r.read(g)]
            return raw if stage is None else stage(raw)

        label = f"{name} (leitor)" if stage else name
        if args.reliability:
            print(f"## {label}\n\n{reliability(recognize, crops)}\n")
            continue
        results.append(bench(label, recognize, crops, top=args.top))
    if args.reliability:
        return 0
    if args.json:
        print(json.dumps([r.json() for r in results], ensure_ascii=False, indent=2))
    else:
        print(table(results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
