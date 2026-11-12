"""``CorrectedBatchWriter`` em .zip com TIFF Deflate (sem perda), mantendo o DPI.

O Anexo I do Decreto 10.278/2020 exige compressão sem perda: nunca JPEG.
"""

from __future__ import annotations

import hashlib
import io
import logging
import zipfile
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PIL import Image
from PIL.TiffImagePlugin import ImageFileDirectory_v2

from qa_engine.ports import PreservedTags

TIFF_COMPRESSION = "tiff_adobe_deflate"
_TAGS = {"make": 271, "model": 272, "software": 305, "datetime": 306, "artist": 315}
XMP_TAG = 700
log = logging.getLogger("qa_engine.corrected")


def _directory(
    tags: Mapping[str, str], preserved: PreservedTags | None, xmp: bytes | None
) -> ImageFileDirectory_v2:
    ifd = ImageFileDirectory_v2()
    # Texto TIFF: o Pillow lê em latin-1; gravar os mesmos bytes devolve o original intacto
    # (acentos inclusive), em vez de trocá-los por "?".
    for number, (kind, value) in (preserved.main if preserved else {}).items():
        ifd[number] = (
            value.encode("latin-1", "replace") if kind == 2 and isinstance(value, str) else value
        )
        ifd.tagtype[number] = kind
    for key, value in tags.items():
        if key in _TAGS and value:
            ifd[_TAGS[key]] = str(value).encode("latin-1", "replace")
            ifd.tagtype[_TAGS[key]] = 2
    packet = preserved.xmp if preserved and preserved.xmp else xmp
    if packet:
        ifd[XMP_TAG] = packet
        ifd.tagtype[XMP_TAG] = 1
    return ifd


def encode_tiff(
    image: NDArray[np.uint8],
    dpi: float | None,
    bilevel: bool,
    tags: Mapping[str, str],
    preserved: PreservedTags | None = None,
    xmp: bytes | None = None,
) -> bytes:
    """Codifica uma página em TIFF Deflate.

    Args:
        image: página em cinza (2D) ou RGB (3D).
        dpi: resolução a gravar (a do original).
        bilevel: grava em 1 bit, como o original monocromático.
        tags: ``make``, ``model``, ``software``, ``datetime``, ``artist`` (têm prioridade).
        preserved: tags do original a manter.
        xmp: pacote XMP com os metadados do Decreto (só se o original não tinha XMP).
    """
    img = Image.fromarray(image)
    if bilevel:
        img = img.convert("L").point(lambda v: 255 if v >= 128 else 0).convert("1")
    kwargs: dict[str, object] = {"compression": TIFF_COMPRESSION}
    if dpi:
        kwargs["dpi"] = (float(dpi), float(dpi))
    try:
        buf = io.BytesIO()
        img.save(buf, format="TIFF", tiffinfo=_directory(tags, preserved, xmp), **kwargs)
    except (OSError, RuntimeError, ValueError, TypeError) as exc:
        if not preserved or not preserved.main:
            raise
        # Uma tag exótica do original que a biblioteca não grava não pode impedir a entrega.
        log.warning("tags do original não preservadas nesta página: %s", exc)
        stripped = PreservedTags({}, preserved.exif, preserved.xmp)
        buf = io.BytesIO()
        img.save(buf, format="TIFF", tiffinfo=_directory(tags, stripped, xmp), **kwargs)
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
        preserved: PreservedTags | None = None,
        xmp: bytes | None = None,
    ) -> str:
        """Grava a página (o TIFF já vem comprimido: o zip só armazena)."""
        data = encode_tiff(image, dpi, bilevel, tags, preserved, xmp)
        self._zip.writestr(self._info(path, zipfile.ZIP_STORED), data)
        return hashlib.sha256(data).hexdigest()

    def add_text(self, path: str, text: str) -> str:
        """Grava um arquivo de texto UTF-8; devolve o SHA-256."""
        data = text.encode("utf-8")
        self._zip.writestr(self._info(path, zipfile.ZIP_DEFLATED), data)
        return hashlib.sha256(data).hexdigest()

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
