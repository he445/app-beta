"""Gravação segura do lote enviado (caminhos relativos e .zip)."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath


class UploadError(ValueError):
    """Envio inválido (caminho perigoso, zip corrompido, tamanho excedido)."""


def safe_relative(name: str) -> PurePosixPath:
    """Normaliza o nome enviado pelo navegador num caminho relativo seguro.

    Rejeita caminhos absolutos, ``..`` e nomes vazios (proteção contra *path traversal*).
    """
    parts = [p for p in name.replace("\\", "/").split("/") if p not in ("", ".")]
    if (
        not parts
        or any(p == ".." for p in parts)
        or name.startswith(("/", "\\"))
        or ":" in parts[0]
    ):
        raise UploadError(f"caminho inválido no envio: {name!r}")
    return PurePosixPath(*parts)


def strip_common_root(paths: list[PurePosixPath]) -> list[PurePosixPath]:
    """Remove a pasta raiz comum (o navegador inclui o nome da pasta arrastada)."""
    if paths and all(len(p.parts) > 1 for p in paths) and len({p.parts[0] for p in paths}) == 1:
        return [PurePosixPath(*p.parts[1:]) for p in paths]
    return paths


def extract_zip(archive: Path, dest: Path, max_bytes: int) -> int:
    """Extrai um .zip com proteção contra *zip slip* e *zip bomb*.

    Returns:
        Quantidade de arquivos extraídos.
    """
    try:
        with zipfile.ZipFile(archive) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()]
            total = sum(m.file_size for m in members)
            if total > max_bytes:
                raise UploadError("conteúdo do .zip excede o limite de envio")
            rels = strip_common_root([safe_relative(m.filename) for m in members])
            for member, rel in zip(members, rels, strict=True):
                target = dest / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(member) as src, target.open("wb") as out:
                    while chunk := src.read(1 << 20):
                        out.write(chunk)
            return len(members)
    except zipfile.BadZipFile as exc:
        raise UploadError("arquivo .zip inválido") from exc
