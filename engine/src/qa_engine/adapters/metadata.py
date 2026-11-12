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
from qa_engine.ports import FileMetadata, PreservedTags

_TIFF_TAGS = {306: "datetime", 271: "make", 272: "model", 305: "software", 315: "artist"}
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

STRUCTURAL_TAGS = frozenset(
    {254, 255, 256, 257, 258, 259, 262, 263, 264, 265, 266, 273, 274, 277, 278, 279, 280}
    | {281, 282, 283, 284, 286, 287, 288, 289, 290, 291, 292, 293, 296, 297, 301, 317}
    | {318, 319, 320, 321, 322, 323, 324, 325, 330, 338, 339, 340, 341, 347, 530, 531}
    | {532, 559, 700, 34377, 34665, 34853, 37724, 40965}
)
"""Tags que descrevem a imagem codificada (tamanho, compressão, faixas, orientação, cores)
ou apontam para outros diretórios: o gravador do lote corrigido refaz ou leva no XMP."""
WRITABLE_TYPES = frozenset(range(1, 13))
"""Tipos TIFF clássicos (BYTE a DOUBLE); IFD e os de 64 bits não são copiados."""
_EXIF_KEEP = {
    36867: "DateTimeOriginal",
    36868: "DateTimeDigitized",
    42016: "ImageUniqueID",
    42033: "BodySerialNumber",
}
_EXIF_MAIN = {
    269: "DocumentName",
    270: "ImageDescription",
    271: "Make",
    272: "Model",
    285: "PageName",
    305: "Software",
    306: "DateTime",
    315: "Artist",
    316: "HostComputer",
    33432: "Copyright",
}


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

    def preserved(self, path: Path, page_in_file: int) -> PreservedTags:
        """Tags da página que vão para o TIFF corrigido (PDF e arquivo ilegível: nenhuma)."""
        if path.suffix.lower() in PDF_SUFFIXES:
            return PreservedTags()
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                return _preserved_image(path, page_in_file)
        except (OSError, UnidentifiedImageError, ValueError, EOFError):
            return PreservedTags()


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


def _preserved_image(path: Path, page_in_file: int) -> PreservedTags:
    main: dict[int, tuple[int, Any]] = {}
    with Image.open(path) as img:
        if page_in_file:
            img.seek(page_in_file)
        directory = getattr(img, "tag_v2", None)
        if directory is not None:
            for number, value in directory.items():
                kind = directory.tagtype.get(number)
                if number in STRUCTURAL_TAGS or kind not in WRITABLE_TYPES:
                    continue
                if isinstance(value, dict):
                    continue
                main[number] = (int(kind), value)
        exif = img.getexif()
        if directory is None:
            # JPEG e PNG: as tags de captura do EXIF viram tags TIFF de texto.
            for number in _EXIF_MAIN:
                text = exif.get(number)
                if text:
                    main[number] = (2, str(text).strip("\x00 "))
        sub = exif.get_ifd(_EXIF_IFD)
        extra = {name: str(sub[n]).strip("\x00 ") for n, name in _EXIF_KEEP.items() if sub.get(n)}
        raw = directory.get(700) if directory is not None else None
        xmp = raw if isinstance(raw, bytes) and raw.strip() else img.info.get("xmp")
        if isinstance(xmp, str):
            xmp = xmp.encode("utf-8")
    return PreservedTags(main, extra, xmp or None)


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
