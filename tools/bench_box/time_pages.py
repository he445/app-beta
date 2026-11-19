"""Cronômetro por página: roda ``qa analyze`` em série medindo cada ``analyze_page``.

Grava um JSON com o tempo total, o tempo de cada página e o ângulo de inclinação medido
(``skew``, mesmo quando não sinaliza), para o banco de regressão conferir tempo e precisão.
A primeira página inclui a carga dos modelos.

Uso::

    uv run --project engine python tools/bench_box/time_pages.py "<caixa>" \
        --profile profiles/sos-piloto.yaml --models models --out <saida> tempos.json
"""

from __future__ import annotations

import json
import math
import sys
import time
from typing import Any

import qa_engine.application.analyze as analyze
from qa_engine.entrypoints.cli.main import main as cli_main


def run(argv: list[str], out_json: str) -> dict[str, Any]:
    """Roda a análise em série e grava os tempos."""
    original = analyze.analyze_page
    pages: list[dict[str, Any]] = []
    root = argv[0]

    def timed(task: Any, *args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = original(task, *args, **kwargs)
        elapsed = time.perf_counter() - start
        skew = result.observations.get("skew") if result.observations else None
        angle = skew.values.get("angle") if skew is not None and skew.eligible else None
        rel = str(task.path)[len(root) :].lstrip("/")
        pages.append(
            {
                "file": rel,
                "page_in_file": task.page_in_file,
                "seconds": round(elapsed, 4),
                "skew_deg": None if angle is None or math.isnan(angle) else round(angle, 3),
            }
        )
        return result

    analyze.analyze_page = timed
    start = time.perf_counter()
    try:
        cli_main(["analyze", *argv, "--workers", "1"])
    except SystemExit:
        pass
    finally:
        analyze.analyze_page = original
    data = {"total_seconds": round(time.perf_counter() - start, 2), "pages": pages}
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
    return data


def main() -> None:
    """Ponto de entrada: os argumentos de ``qa analyze`` e, por último, o JSON de saída."""
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    data = run(sys.argv[1:-1], sys.argv[-1])
    secs = sorted(p["seconds"] for p in data["pages"][1:])
    if secs:
        print(
            f"total {data['total_seconds']} s, {len(data['pages'])} páginas, "
            f"mediana {secs[len(secs) // 2]:.3f} s"
        )


if __name__ == "__main__":
    main()
