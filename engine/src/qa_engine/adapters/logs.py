"""Log em arquivo com rotação, sem conteúdo de documento (LGPD).

O log grava contagens, tempos, identificadores e erros. Nunca imagem nem texto
lido de página; caminhos absolutos do computador são mascarados.
"""

from __future__ import annotations

import logging
import logging.handlers
import re
import traceback
from datetime import UTC, datetime
from pathlib import Path

LOG_FILE = "qa.log"
MAX_BYTES = 5 * 1024 * 1024
BACKUPS = 10
_ABSOLUTE = re.compile(
    r"(?:[A-Za-z]:\\|\\\\\?\\|\\\\)[^\s'\"<>|]+"  # C:\..., \\?\..., \\servidor\...
    r"|(?<![\w.])/(?:home|Users|mnt|media|srv|root|tmp)/[^\s'\"<>|]+"  # /home/..., /Users/...
)


def mask_paths(text: str) -> str:
    """Troca caminhos absolutos por ``<caminho>``: nome de usuário e de pasta não vão ao log."""
    return _ABSOLUTE.sub("<caminho>", text)


class MaskingFormatter(logging.Formatter):
    """Formatter que mascara caminhos absolutos na mensagem e na pilha."""

    def format(self, record: logging.LogRecord) -> str:
        """Linha do log, já sem caminhos absolutos."""
        return mask_paths(super().format(record))


def setup_file_logging(folder: Path, level: str = "info") -> Path:
    """Liga o log em ``<folder>/qa.log``, com 10 arquivos de 5 MB.

    Returns:
        O caminho do arquivo de log.
    """
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / LOG_FILE
    handler = logging.handlers.RotatingFileHandler(
        path, maxBytes=MAX_BYTES, backupCount=BACKUPS, encoding="utf-8"
    )
    handler.setFormatter(MaskingFormatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers = [
        h for h in root.handlers if not isinstance(h, logging.handlers.RotatingFileHandler)
    ]
    root.addHandler(handler)
    root.setLevel(level.upper())
    return path


def write_crash(folder: Path, error: BaseException, version: str) -> Path:
    """Grava o arquivo de queda da abertura do programa e devolve o caminho."""
    folder.mkdir(parents=True, exist_ok=True)
    now = datetime.now(tz=UTC)
    path = folder / f"crash-{now:%Y%m%d-%H%M%S}.txt"
    stack = "".join(traceback.format_exception(error))
    path.write_text(f"QA {version} · {now.isoformat()}\n\n{mask_paths(stack)}", encoding="utf-8")
    return path
