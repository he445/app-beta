"""Lotes de demonstração prontos no servidor (ADR-0010).

No celular não há como escolher uma pasta e um lote realista tem dezenas de
megabytes: a demonstração usa lotes sintéticos gerados no build da imagem
(``tools/synth``) e copiados para um lote novo a cada uso. O original da
demonstração nunca é alterado (princípio 2).
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

from qa_engine.adapters.images import SUPPORTED_SUFFIXES

ANSWER_KEY = "gabarito.json"
"""O gabarito fica no servidor: a ferramenta não pode ver a resposta."""


@dataclass(frozen=True, slots=True)
class DemoBatch:
    """Lote de demonstração disponível."""

    name: str
    pages: int
    documents: int


def _pages(folder: Path) -> list[Path]:
    return [
        p
        for p in folder.rglob("*")
        if p.is_file() and p.suffix.lower() in SUPPORTED_SUFFIXES and not p.name.startswith(".")
    ]


def list_demo_batches(root: Path | None) -> list[DemoBatch]:
    """Lotes de demonstração em ``root`` (uma subpasta por lote), em ordem de nome."""
    if root is None or not root.is_dir():
        return []
    batches = []
    for folder in sorted(p for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")):
        pages = _pages(folder)
        if pages:
            batches.append(DemoBatch(folder.name, len(pages), len({p.parent for p in pages})))
    return batches


def copy_demo_batch(root: Path | None, name: str, dest: Path) -> DemoBatch:
    """Copia o lote ``name`` para ``dest`` (sem o gabarito).

    Raises:
        LookupError: se o lote não existe (o nome nunca vira caminho sem passar
            pela lista, o que impede ``../``).
    """
    found = next((b for b in list_demo_batches(root) if b.name == name), None)
    if found is None or root is None:
        raise LookupError(f"lote de demonstração {name!r} não encontrado")
    shutil.copytree(
        root / found.name,
        dest,
        ignore=shutil.ignore_patterns(ANSWER_KEY, ".*"),
        dirs_exist_ok=True,
    )
    return found
