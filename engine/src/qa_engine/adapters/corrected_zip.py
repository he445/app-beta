"""``CorrectedBatchWriter`` em .zip com TIFF Deflate (sem perda), mantendo o DPI.

O Anexo I do Decreto 10.278/2020 exige compressão sem perda: nunca JPEG.
"""

from __future__ import annotations

import hashlib
import io
import zipfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image

TIFF_COMPRESSION = "tiff_adobe_deflate"
_TAGS = {"make": 271, "model": 272, "software": 305, "datetime": 306, "artist": 315}


def encode_tiff(
    image: NDArray[np.uint8], dpi: float | None, bilevel: bool, tags: Mapping[str, str]
) -> bytes:
    """Codifica uma página em TIFF Deflate.

    Args:
        image: página em cinza (2D) ou RGB (3D).
        dpi: resolução a gravar (a do original).
        bilevel: grava em 1 bit, como o original monocromático.
        tags: ``make``, ``model``, ``software``, ``datetime``, ``artist``.
    """
    img = Image.fromarray(image)
    if bilevel:
        img = img.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("1")
    info = {_TAGS[k]: str(v) for k, v in tags.items() if k in _TAGS and v}
    buf = io.BytesIO()
    kwargs: dict[str, object] = {"compression": TIFF_COMPRESSION, "tiffinfo": info}
    if dpi:
        kwargs["dpi"] = (float(dpi), float(dpi))
    img.save(buf, format="TIFF", **kwargs)
    return buf.getvalue()


class ZipTiffWriter:
    """Escreve o lote corrigido num .zip temporário e o publica no ``close``."""

    def __init__(self, target: Path, when: datetime) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        self.target = target
        self._partial = target.with_name(target.name + ".part")
        self._zip = zipfile.ZipFile(self._partial, "w")
        self._date = (when.year, when.month, when.day, when.hour, when.minute, when.second)

    def _info(self, path: str, compress: int) -> zipfile.ZipInfo:
        info = zipfile.ZipInfo(path, date_time=self._date)
        info.compress_type = compress
        return info

    def add_page(
        self,
        path: str,
        image: NDArray[np.uint8],
        dpi: float | None,
        bilevel: bool,
        tags: Mapping[str, str],
    ) -> str:
        """Grava a página (o TIFF já vem comprimido: o zip só armazena)."""
        data = encode_tiff(image, dpi, bilevel, tags)
        self._zip.writestr(self._info(path, zipfile.ZIP_STORED), data)
        return hashlib.sha256(data).hexdigest()

    def add_text(self, path: str, text: str) -> None:
        """Grava um arquivo de texto UTF-8."""
        self._zip.writestr(self._info(path, zipfile.ZIP_DEFLATED), text.encode("utf-8"))

    def close(self) -> tuple[Path, str, int]:
        """Fecha o zip e o move para o destino de forma atômica."""
        self._zip.close()
        self._partial.replace(self.target)
        data = self.target.read_bytes()
        return self.target, hashlib.sha256(data).hexdigest(), len(data)

    def abort(self) -> None:
        """Fecha e apaga o zip parcial."""
        self._zip.close()
        self._partial.unlink(missing_ok=True)
