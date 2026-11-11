r"""``BatchFolder`` para pastas locais e de rede, lidas no lugar (ADR-0013).

No Windows, caminhos absolutos ganham o prefixo ``\\?\`` (``\\?\UNC\`` para
pastas de rede): assim o sistema abre caminhos com mais de 260 caracteres sem
exigir a configuração ``LongPathsEnabled``.
"""

from __future__ import annotations

import ntpath
import os
import sys
from pathlib import Path, PurePath

from qa_engine.adapters.metadata import sha256_of
from qa_engine.ports import FileStamp

EXTENDED = "\\\\?\\"
EXTENDED_UNC = "\\\\?\\UNC\\"


def extended_path(path: str) -> str:
    r"""Forma estendida de um caminho absoluto do Windows.

    ``C:\a`` → ``\\?\C:\a``; ``\\servidor\pasta`` → ``\\?\UNC\servidor\pasta``. Caminho já
    estendido, relativo ou de outro sistema volta igual.
    """
    if path.startswith(EXTENDED) or not ntpath.isabs(path):
        return path
    normalized = ntpath.normpath(path)
    if normalized.startswith("\\\\"):
        return EXTENDED_UNC + normalized[2:]
    return EXTENDED + normalized


def display_path(path: str) -> str:
    r"""Caminho para mostrar à pessoa, sem o prefixo ``\\?\``."""
    if path.startswith(EXTENDED_UNC):
        return "\\\\" + path[len(EXTENDED_UNC) :]
    if path.startswith(EXTENDED):
        return path[len(EXTENDED) :]
    return path


def _norm(path: PurePath | str, windows: bool) -> str:
    text = display_path(str(path))
    if windows:
        return ntpath.normcase(ntpath.normpath(text)).rstrip("\\") + "\\"
    return os.path.normpath(text).rstrip("/") + "/"


def is_within(
    path: PurePath | str, roots: tuple[PurePath, ...], windows: bool | None = None
) -> bool:
    """Se ``path`` está dentro de alguma das raízes (vazio = qualquer lugar).

    No Windows a comparação ignora maiúsculas e o tipo de barra.
    """
    if not roots:
        return True
    win = sys.platform == "win32" if windows is None else windows
    target = _norm(path, win)
    return any(target.startswith(_norm(root, win)) for root in roots)


class LocalFolderSource:
    """Lê a pasta do lote no lugar, só para leitura."""

    def resolve(self, path: str) -> Path:
        """Caminho absoluto e estendido; erro claro se não existe ou não é pasta."""
        raw = os.path.expandvars(os.path.expanduser(path.strip().strip('"')))
        absolute = os.path.abspath(raw)
        if sys.platform == "win32":
            absolute = extended_path(absolute)
        resolved = Path(absolute)
        if not resolved.exists():
            raise FileNotFoundError(f"pasta não encontrada: {display_path(absolute)}")
        if not resolved.is_dir():
            raise NotADirectoryError(f"não é uma pasta: {display_path(absolute)}")
        return resolved

    def listing(self, root: Path) -> dict[str, FileStamp]:
        """Arquivos do lote com tamanho e data; ocultos e ilegíveis ficam de fora."""
        stamps: dict[str, FileStamp] = {}
        for current, dirs, files in os.walk(root):
            dirs[:] = sorted(d for d in dirs if not d.startswith("."))
            for name in sorted(files):
                if name.startswith("."):
                    continue
                full = Path(current) / name
                try:
                    stat = full.stat()
                except OSError:
                    continue
                rel = full.relative_to(root).as_posix()
                stamps[rel] = FileStamp(stat.st_size, stat.st_mtime_ns)
        return stamps

    def sha256(self, path: Path) -> str | None:
        """SHA-256, ou ``None`` se o arquivo está bloqueado ou sem permissão de leitura."""
        try:
            return sha256_of(path)
        except OSError:
            return None
