"""Cópia do banco local (decisões e auditoria) para a pasta compartilhada.

Cópia consistente pela API de backup do SQLite, mesmo com o programa aberto. Uma pasta
por máquina; ficam as :data:`KEEP` mais novas. As cópias seguem as mesmas regras de
retenção e LGPD dos dados do programa.
"""

from __future__ import annotations

import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

KEEP = 14
PREFIX = "qa-"
SUFFIX = ".sqlite3"


def backup_name(now: datetime) -> str:
    """Nome da cópia: ``qa-AAAAMMDD-HHMMSS.sqlite3`` (ordena pela data)."""
    return f"{PREFIX}{now:%Y%m%d-%H%M%S}{SUFFIX}"


def list_backups(folder: Path) -> list[Path]:
    """Cópias de uma pasta, da mais antiga para a mais nova."""
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.name.startswith(PREFIX) and p.suffix == SUFFIX)


def copy_database(source: sqlite3.Connection, target: Path) -> Path:
    """Copia o banco aberto para ``target`` (grava em temporário e renomeia)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    part.unlink(missing_ok=True)
    dest = sqlite3.connect(part)
    try:
        source.backup(dest)
    finally:
        dest.close()
    part.replace(target)
    return target


def prune(folder: Path, keep: int = KEEP) -> list[Path]:
    """Apaga as cópias além das ``keep`` mais novas; devolve as apagadas."""
    old = list_backups(folder)[:-keep] if keep > 0 else list_backups(folder)
    for path in old:
        path.unlink(missing_ok=True)
    return old


def check(path: Path) -> str | None:
    """``None`` se a cópia está íntegra e é um banco do programa; senão o motivo."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return f"não abre: {exc}"
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            return f"banco corrompido: {result[0] if result else 'sem resposta'}"
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not {"batches", "decisions", "schema_migrations"} <= tables:
            return "não é um banco do programa"
    except sqlite3.Error as exc:
        return f"não lê: {exc}"
    finally:
        conn.close()
    return None


def restore(backup: Path, database: Path, now: datetime) -> Path | None:
    """Põe a cópia no lugar do banco; o banco atual é guardado ao lado.

    Returns:
        Onde ficou o banco anterior (ou ``None`` se não havia).

    Raises:
        ValueError: a cópia não está íntegra ou não é um banco do programa.
    """
    problem = check(backup)
    if problem is not None:
        raise ValueError(problem)
    database.parent.mkdir(parents=True, exist_ok=True)
    kept = None
    if database.exists():
        kept = database.with_name(f"{database.name}.antes-da-restauracao-{now:%Y%m%d-%H%M%S}")
        shutil.copy2(database, kept)
    for extra in ("-wal", "-shm"):
        Path(f"{database}{extra}").unlink(missing_ok=True)
    part = database.with_name(database.name + ".restaurando")
    shutil.copy2(backup, part)
    part.replace(database)
    return kept
