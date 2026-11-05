"""``NumberingReader`` a partir de um arquivo ``numbering.json`` no lote.

Formato (``contracts/schemas/numbering-sidecar.schema.json``)::

    {"pages": {"doc1/0001.png#0": [{"struck": false,
                                     "readings": [{"text": "12", "confidence": 0.93}]}]}}

Na PoC esse arquivo vem do leitor de manuscrito rodando fora do motor, da base
sintética ou de numeração digitada pelo revisor. O adaptador TrOCR/PaddleOCR-VL
(seção 6 do ADD) implementará a mesma porta.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from qa_engine.domain.sequencing import Mark, Reading

SIDECAR_NAME = "numbering.json"


def marks_from_json(items: Sequence[Mapping[str, object]]) -> tuple[Mark, ...]:
    """Converte a lista de marcas do JSON em objetos de domínio."""
    marks: list[Mark] = []
    for item in items:
        readings_raw = item.get("readings", [])
        if not isinstance(readings_raw, list):
            continue
        readings = tuple(
            Reading(str(r["text"]), float(r["confidence"]))
            for r in readings_raw
            if isinstance(r, dict)
        )
        marks.append(Mark(readings, bool(item.get("struck", False))))
    return tuple(marks)


class SidecarNumberingReader:
    """Lê ``numbering.json`` na raiz do lote; páginas ausentes ficam sem marcas."""

    def read(self, batch_root: Path, page_keys: Sequence[str]) -> Mapping[str, Sequence[Mark]]:
        """Marcas por chave de página."""
        path = batch_root / SIDECAR_NAME
        if not path.is_file():
            return {}
        data = json.loads(path.read_text("utf-8"))
        pages = data.get("pages", {})
        return {key: marks_from_json(pages[key]) for key in page_keys if key in pages}
