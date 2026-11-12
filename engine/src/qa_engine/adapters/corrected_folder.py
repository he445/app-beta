"""``CorrectedBatchWriter`` em pasta: grava num temporário e renomeia só no fim.

Nunca fica uma pasta com o nome final pela metade: enquanto grava, a pasta se
chama ``.<nome>.part`` (oculta); ``close`` a renomeia, ``abort`` a apaga.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from qa_engine.adapters.corrected_zip import encode_tiff

MANIFEST = "manifest.json"


def folder_name(batch_name: str, when: datetime) -> str:
    """``<lote>-corrigido-<AAAAMMDD-HHMMSS>``, sem caracteres proibidos no Windows."""
    safe = "".join("_" if c in '<>:"/\\|?*' or ord(c) < 32 else c for c in batch_name).strip(". ")
    return f"{safe or 'lote'}-corrigido-{when:%Y%m%d-%H%M%S}"


class FolderTiffWriter:
    """Escreve o lote corrigido numa pasta nova dentro de ``output_dir``."""

    def __init__(self, output_dir: Path, batch_name: str, when: datetime) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        name = folder_name(batch_name, when)
        self.target = output_dir / name
        suffix = 1
        while self.target.exists():
            suffix += 1
            self.target = output_dir / f"{name}-{suffix}"
        self._partial = output_dir / f".{self.target.name}.part"
        shutil.rmtree(self._partial, ignore_errors=True)
        self._partial.mkdir()
        self._size = 0

    def _path(self, rel: str) -> Path:
        path = (self._partial / rel).resolve()
        if not path.is_relative_to(self._partial.resolve()):
            raise ValueError(f"caminho fora da pasta do lote corrigido: {rel}")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def add_page(
        self,
        path: str,
        image: NDArray[np.uint8],
        dpi: float | None,
        bilevel: bool,
        tags: Mapping[str, str],
        xmp: bytes | None = None,
    ) -> str:
        """Grava a página em TIFF Deflate; devolve o SHA-256 do arquivo."""
        data = encode_tiff(image, dpi, bilevel, tags, xmp)
        self._path(path).write_bytes(data)
        self._size += len(data)
        return hashlib.sha256(data).hexdigest()

    def add_text(self, path: str, text: str) -> None:
        """Grava um arquivo de texto UTF-8."""
        data = text.encode("utf-8")
        self._path(path).write_bytes(data)
        self._size += len(data)

    def close(self) -> tuple[Path, str, int]:
        """Renomeia a pasta temporária para o nome final.

        Returns:
            ``(pasta, SHA-256 do manifest.json, soma dos tamanhos)``.
        """
        manifest = self._partial / MANIFEST
        sha = hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.is_file() else ""
        self._partial.rename(self.target)
        return self.target, sha, self._size

    def abort(self) -> None:
        """Apaga a pasta temporária."""
        shutil.rmtree(self._partial, ignore_errors=True)
