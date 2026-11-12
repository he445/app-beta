"""``MetadataReader`` com Pillow e pypdfium2.

O ExifTool (ADR-0004) é a referência para cobertura total de tags e entra como
outro adaptador, em processo externo, numa fase seguinte.
"""

from __future__ import annotations

import hashlib
import warnings
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium
from PIL import Image, ImageSequence, UnidentifiedImageError

from qa_engine.adapters.images import PDF_SUFFIXES
from qa_engine.ports import FileMetadata

_TIFF_TAGS = {
    306: "datetime",
    271: "make",
    272: "model",
    305: "software",
    315: "artist",
    269: "document_name",
    270: "description",
    285: "page_name",
    316: "host_computer",
    33432: "copyright",
}
_EXIF_IFD = 0x8769
_EXIF_DATETIME_ORIGINAL = 36867
_EXIF_BODY_SERIAL = 42033
_TIFF_COMPRESSION = {
    1: "none",
    2: "ccitt_rle",
    3: "group3",
    4: "group4",
    5: "lzw",
    6: "jpeg",
    7: "jpeg",
    8: "deflate",
    32773: "packbits",
    32946: "deflate",
}
LOSSY_COMPRESSIONS = {"jpeg"}
UNREADABLE_SHA256 = hashlib.sha256(b"").hexdigest()


def sha256_of(path: Path) -> str:
    """SHA-256 do arquivo, em blocos de 1 MiB."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


class PillowMetadataReader:
    """Lê tags TIFF, EXIF e o dicionário de informações de PDF."""

    def read(self, path: Path) -> FileMetadata:
        """Metadados do arquivo; tags ilegíveis são simplesmente omitidas."""
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=UTC)
        try:
            sha = sha256_of(path)
        except OSError:
            # Bloqueado por outro programa ou rede fora: a página vira corrupted_file
            # (arquivo inacessível) e o lote segue. SHA-256 do conteúdo vazio no lugar.
            sha = UNREADABLE_SHA256
        suffix = path.suffix.lower()
        tags: dict[str, Any] = {}
        pages = 0
        fmt = suffix.lstrip(".").upper() or "UNKNOWN"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                if suffix in PDF_SUFFIXES:
                    fmt, pages, tags = _read_pdf(path)
                elif stat.st_size:
                    fmt, pages, tags = _read_image(path)
        except (OSError, UnidentifiedImageError, pdfium.PdfiumError, ValueError):
            pass
        return FileMetadata(fmt, stat.st_size, sha, pages, tags, modified)


def _read_image(path: Path) -> tuple[str, int, dict[str, Any]]:
    tags: dict[str, Any] = {}
    with Image.open(path) as img:
        fmt = img.format or "UNKNOWN"
        tags["width_px"], tags["height_px"] = img.size
        tags["bits"] = {"1": 1, "L": 8, "P": 8, "RGB": 24, "RGBA": 32, "I;16": 16}.get(img.mode)
        tags["mode"] = img.mode
        dpi = img.info.get("dpi")
        if dpi and float(dpi[0]) > 1:
            tags["dpi"] = round(float(dpi[0]), 1)
        exif = img.getexif()
        for tag, name in _TIFF_TAGS.items():
            value = exif.get(tag)
            if value:
                tags[name] = str(value).strip("\x00 ")
        sub = exif.get_ifd(_EXIF_IFD)
        if sub.get(_EXIF_DATETIME_ORIGINAL):
            tags["datetime"] = str(sub[_EXIF_DATETIME_ORIGINAL])
        if sub.get(_EXIF_BODY_SERIAL):
            tags["serial"] = str(sub[_EXIF_BODY_SERIAL])
        if fmt == "TIFF":
            code = getattr(img, "tag_v2", {}).get(259)
            tags["compression"] = _TIFF_COMPRESSION.get(int(code), str(code)) if code else "none"
        elif fmt == "JPEG":
            tags["compression"] = "jpeg"
        elif fmt == "PNG":
            tags["compression"] = "deflate"
        pages = sum(1 for _ in ImageSequence.Iterator(img))
    return fmt, pages, tags


def _read_pdf(path: Path) -> tuple[str, int, dict[str, Any]]:
    pdf = pdfium.PdfDocument(str(path))
    try:
        info = pdf.get_metadata_dict(skip_empty=True)
        tags: dict[str, Any] = {}
        if "CreationDate" in info:
            tags["datetime"] = info["CreationDate"]
        if "Producer" in info:
            tags["software"] = info["Producer"]
        if "Creator" in info:
            tags["make"] = info["Creator"]
        if "Author" in info:
            tags["artist"] = info["Author"]
        version = pdf.get_version()
        return f"PDF-{version / 10:.1f}" if version else "PDF", len(pdf), tags
    finally:
        pdf.close()
