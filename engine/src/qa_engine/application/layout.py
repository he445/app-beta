"""Descoberta de documentos e páginas numa pasta de lote.

Especificação: ``docs/especificacoes/batch-layout.md``.
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

from qa_engine.adapters.images import SUPPORTED_SUFFIXES

RESERVED = {"manifest.csv", "index.csv", "numbering.json"}
_NUM_RE = re.compile(r"(\d+)")


def natural_key(text: str) -> list[object]:
    """Ordenação natural: ``p2`` antes de ``p10``."""
    return [int(t) if t.isdigit() else t.lower() for t in _NUM_RE.split(text)]


@dataclass(frozen=True, slots=True)
class FileRef:
    """Arquivo de imagem do lote, com caminho relativo em barras ``/``."""

    path: Path
    rel: str


@dataclass(frozen=True, slots=True)
class DocumentLayout:
    """Documento descoberto: nome e arquivos em ordem."""

    name: str
    files: tuple[FileRef, ...]
    multipage_file: bool
    """Verdadeiro quando o documento é um único arquivo multipágina (PDF, TIFF)."""


def discover(root: Path, multipage: set[str]) -> list[DocumentLayout]:
    """Agrupa os arquivos do lote em documentos.

    Regras: cada arquivo multipágina é um documento; as imagens de página única
    de uma mesma pasta formam um documento com o nome da pasta (imagens soltas
    na raiz usam o nome do lote).

    Args:
        root: pasta do lote.
        multipage: caminhos relativos dos arquivos com mais de uma página.
    """
    files = sorted(
        (
            p
            for p in root.rglob("*")
            if p.is_file()
            and not any(part.startswith(".") for part in p.relative_to(root).parts)
            and p.name not in RESERVED
            and p.suffix.lower() in SUPPORTED_SUFFIXES
        ),
        key=lambda p: natural_key(p.relative_to(root).as_posix()),
    )
    documents: list[DocumentLayout] = []
    folders: dict[str, list[FileRef]] = {}
    for path in files:
        ref = FileRef(path, path.relative_to(root).as_posix())
        if ref.rel in multipage or path.suffix.lower() == ".pdf":
            documents.append(DocumentLayout(ref.rel.rsplit(".", 1)[0], (ref,), True))
        else:
            parent = path.parent.relative_to(root).as_posix()
            folders.setdefault(root.name if parent == "." else parent, []).append(ref)
    documents.extend(DocumentLayout(name, tuple(refs), False) for name, refs in folders.items())
    return sorted(documents, key=lambda d: natural_key(d.name))


def read_manifest(root: Path) -> dict[str, int]:
    """Contagem declarada por documento, de ``manifest.csv`` (colunas ``document,pages``)."""
    path = root / "manifest.csv"
    if not path.is_file():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {
            row["document"].strip(): int(row["pages"])
            for row in csv.DictReader(handle)
            if row.get("document") and row.get("pages")
        }
