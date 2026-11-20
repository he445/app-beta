"""Leitor de metadados: o EXIF do PNG sai sem decodificar a imagem."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from qa_engine.adapters import metadata
from qa_engine.adapters.metadata import PillowMetadataReader


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def _png_with_exif_after_pixels(path: Path) -> None:
    Image.fromarray(np.full((40, 30), 200, np.uint8)).save(path)
    exif = Image.Exif()
    exif[271] = "Fujitsu"
    exif[272] = "fi-7160"
    raw = path.read_bytes()
    end = raw.rindex(b"IEND") - 4
    path.write_bytes(raw[:end] + _chunk(b"eXIf", exif.tobytes()) + raw[end:])


def test_png_exif_after_pixels_is_read_without_decoding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "p.png"
    _png_with_exif_after_pixels(path)
    with Image.open(path) as img:
        expected = dict(img.getexif())
    assert expected  # o Pillow acha o mesmo EXIF decodificando

    def no_decode(self: Image.Image) -> None:
        raise AssertionError("decodificou a imagem")

    monkeypatch.setattr(Image.Image, "getexif", no_decode)
    tags = PillowMetadataReader().read(path).tags
    assert tags["make"] == "Fujitsu"
    assert tags["model"] == "fi-7160"


def test_png_without_exif_has_no_capture_tags(tmp_path: Path) -> None:
    path = tmp_path / "p.png"
    Image.fromarray(np.full((40, 30), 200, np.uint8)).save(path, dpi=(300, 300))
    tags = PillowMetadataReader().read(path).tags
    assert tags["dpi"] == 300.0
    assert "make" not in tags


def test_png_text_after_pixels_falls_back_to_pillow(tmp_path: Path) -> None:
    path = tmp_path / "p.png"
    Image.fromarray(np.full((40, 30), 200, np.uint8)).save(path)
    raw = path.read_bytes()
    end = raw.rindex(b"IEND") - 4
    path.write_bytes(raw[:end] + _chunk(b"tEXt", b"Comment\x00x") + raw[end:])
    calls: list[int] = []
    original = Image.Image.getexif

    def spy(self: Image.Image) -> Image.Exif:
        calls.append(1)
        return original(self)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(Image.Image, "getexif", spy)
        with Image.open(path) as img:
            metadata._exif(img, path)
    assert calls == [1]
