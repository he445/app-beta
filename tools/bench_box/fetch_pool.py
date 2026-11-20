"""Baixa as folhas de origem da caixa de regressão (RVL-CDIP) e grava em PNG cinza.

As folhas listadas em ``folhas-limpas.txt`` vêm do subconjunto público
``vaclavpechtor/rvl_cdip-small-200`` (Hugging Face), pasta ``train/<classe>/``. O nome
``<classe>__<id>.png`` diz de onde veio cada uma. Ver ``docs/testes/caixa-de-regressao.md``
(a licença do RVL-CDIP precisa ser conferida antes de redistribuir as imagens).

Uso::

    python3 tools/bench_box/fetch_pool.py tools/bench_box/folhas-limpas.txt <pasta_das_folhas>
"""

from __future__ import annotations

import argparse
import io
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image

BASE = "https://huggingface.co/datasets/vaclavpechtor/rvl_cdip-small-200/resolve/main/train"


def fetch(name: str, out: Path) -> str | None:
    """Baixa uma folha; devolve o erro ou ``None``."""
    target = out / name
    if target.is_file():
        return None
    label, ident = name[: -len(".png")].split("__", 1)
    try:
        with urllib.request.urlopen(f"{BASE}/{label}/{ident}.tif", timeout=60) as resp:
            data = resp.read()
        Image.open(io.BytesIO(data)).convert("L").save(target)
    except Exception as exc:
        return f"{name}: {exc}"
    return None


def main() -> None:
    """Ponto de entrada."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("lista", type=Path)
    parser.add_argument("saida", type=Path)
    args = parser.parse_args()
    args.saida.mkdir(parents=True, exist_ok=True)
    names = [line.strip() for line in args.lista.read_text("utf-8").splitlines() if line.strip()]
    with ThreadPoolExecutor(8) as pool:
        errors = [e for e in pool.map(lambda n: fetch(n, args.saida), names) if e]
    print(f"{len(names) - len(errors)} folhas em {args.saida}")
    for e in errors:
        print(e, file=sys.stderr)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
