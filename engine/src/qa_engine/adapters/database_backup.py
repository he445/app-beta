r"""Cópia do banco local para a pasta compartilhada e restauração (``qa backup restore``).

Decisões e auditoria vivem no SQLite de cada máquina; se o computador pifar no meio do
beta, elas sumiriam. Uma vez por dia e ao fechar o programa, a API de backup do SQLite
faz uma cópia consistente (mesmo com o programa gravando) em
``<backup_dir>\<máquina>\<usuário>\qa-AAAAMMDD-HHMMSS.sqlite3``, guardando as 14 mais
recentes. Especificação: ``docs/especificacoes/backup-do-banco.md``.
"""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from importlib import resources
from pathlib import Path

KEEP = 14
"""Cópias guardadas por máquina e usuário."""
EVERY = timedelta(hours=24)
"""Intervalo entre as cópias diárias."""
RETRY = timedelta(hours=1)
"""Depois de uma falha (pasta de rede fora do ar), nova tentativa só depois disso."""
_NAME = re.compile(r"^qa-(\d{8})-(\d{6})\.sqlite3$")


class BackupError(Exception):
    """A cópia não pode ser restaurada (corrompida, de versão mais nova, banco em uso)."""


@dataclass(frozen=True, slots=True)
class BackupFile:
    """Uma cópia do banco."""

    path: Path
    taken_at: datetime


def safe_part(text: str) -> str:
    """Nome de pasta seguro no Windows (máquina e usuário)."""
    cleaned = "".join("_" if ch in '\\/:*?"<>|' or ord(ch) < 32 else ch for ch in text)
    return cleaned.strip(" .") or "sem-nome"


def backup_folder(root: Path, machine: str, user: str) -> Path:
    """Pasta das cópias desta máquina e deste usuário dentro de ``root``."""
    return root / safe_part(machine) / safe_part(user)


def file_name(when: datetime) -> str:
    """``qa-AAAAMMDD-HHMMSS.sqlite3`` (UTC)."""
    return f"qa-{when.astimezone(UTC):%Y%m%d-%H%M%S}.sqlite3"


def list_backups(folder: Path) -> list[BackupFile]:
    """Cópias da pasta, da mais nova para a mais antiga (pasta inacessível: lista vazia)."""
    found: list[BackupFile] = []
    try:
        entries = list(folder.iterdir()) if folder.is_dir() else []
    except OSError:
        return found
    for path in entries:
        match = _NAME.match(path.name)
        if match and path.is_file():
            taken = datetime.strptime(match[1] + match[2], "%Y%m%d%H%M%S").replace(tzinfo=UTC)
            found.append(BackupFile(path, taken))
    return sorted(found, key=lambda b: b.taken_at, reverse=True)


def all_backups(root: Path) -> list[tuple[str, str, BackupFile]]:
    """Cópias de todas as máquinas e usuários de ``root`` (máquina, usuário, cópia)."""
    out: list[tuple[str, str, BackupFile]] = []
    try:
        machines = sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []
    except OSError:
        return out
    for machine in machines:
        for user in sorted(p for p in machine.iterdir() if p.is_dir()):
            out.extend((machine.name, user.name, b) for b in list_backups(user))
    return out


def take_backup(db: Path, folder: Path, now: datetime, keep: int = KEEP) -> Path:
    """Copia o banco de forma consistente e apaga as cópias além das ``keep`` mais novas.

    A cópia é gravada num arquivo parcial e renomeada no fim: uma cópia interrompida
    nunca parece pronta.

    Raises:
        OSError: a pasta não está acessível.
        sqlite3.Error: o banco não pôde ser lido.
    """
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / file_name(now)
    partial = target.with_name(target.name + ".part")
    partial.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    partial.replace(target)
    for old in list_backups(folder)[keep:]:
        old.path.unlink(missing_ok=True)
    return target


def known_migrations() -> set[str]:
    """Migrações que esta versão do programa conhece."""
    folder = resources.files("qa_engine.adapters") / "migrations"
    return {item.name for item in folder.iterdir() if item.name.endswith(".sql")}


def check_backup(path: Path, known: Iterable[str] | None = None) -> list[str]:
    """Problemas que impedem restaurar a cópia (lista vazia = pode restaurar)."""
    if not path.is_file():
        return [f"arquivo não encontrado: {path}"]
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        return [f"não é um banco do programa: {exc}"]
    try:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            return [f"cópia corrompida: {result[0] if result else 'sem resposta'}"]
        applied = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
    except sqlite3.Error as exc:
        return [f"não é um banco do programa: {exc}"]
    finally:
        conn.close()
    newer = sorted(applied - set(known if known is not None else known_migrations()))
    if newer:
        return [
            "a cópia é de uma versão mais nova do programa (migrações "
            + ", ".join(newer)
            + "): abra-a com essa versão"
        ]
    return []


def restore_backup(backup: Path, db: Path, now: datetime) -> Path | None:
    """Troca o banco pela cópia; o banco atual, se existir, é guardado ao lado antes.

    Chamar só com o programa fechado (quem chama confere a trava de instância).

    Returns:
        O arquivo com o banco que existia antes, ou ``None`` numa máquina limpa.

    Raises:
        BackupError: a cópia não pode ser restaurada.
    """
    problems = check_backup(backup)
    if problems:
        raise BackupError("; ".join(problems))
    db.parent.mkdir(parents=True, exist_ok=True)
    previous: Path | None = None
    if db.is_file():
        previous = db.with_name(
            f"{db.name}.antes-da-restauracao-{now.astimezone(UTC):%Y%m%d-%H%M%S}"
        )
        current = sqlite3.connect(db)
        try:
            saved = sqlite3.connect(previous)
            try:
                current.backup(saved)
            finally:
                saved.close()
            # Leva o diário (WAL) para dentro do banco e o desliga: os arquivos -wal e -shm
            # somem sem ser apagados à força (no Windows, apagar um em uso falha).
            current.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            current.execute("PRAGMA journal_mode=DELETE")
        except sqlite3.OperationalError as exc:
            raise BackupError(
                f"o banco está em uso; feche o programa e tente de novo ({exc})"
            ) from exc
        finally:
            current.close()
    try:
        for suffix in ("-wal", "-shm"):
            db.with_name(db.name + suffix).unlink(missing_ok=True)
    except PermissionError as exc:
        raise BackupError("o banco está em uso; feche o programa e tente de novo") from exc
    partial = db.with_name(db.name + ".restaurando")
    partial.unlink(missing_ok=True)
    source = sqlite3.connect(f"file:{backup.as_posix()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    try:
        partial.replace(db)
    except PermissionError as exc:
        partial.unlink(missing_ok=True)
        raise BackupError("o banco está em uso; feche o programa e tente de novo") from exc
    return previous


# Troca de versão ------------------------------------------------------------------------

UPDATES_FOLDER = "atualizacoes"
"""Dentro de ``data_dir``: cópias do banco feitas antes de cada atualização."""
KEEP_UPDATES = 5


class DatabaseNewerError(Exception):
    """O banco foi atualizado por uma versão mais nova do programa que esta."""

    def __init__(self, migrations: Sequence[str], version: str | None) -> None:
        self.migrations = list(migrations)
        self.version = version
        label = f"pela versão {version}" if version else "por uma versão mais nova"
        super().__init__(f"o banco deste computador foi atualizado {label} do programa")


def _applied(db: Path) -> tuple[set[str], str | None]:
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        applied = {r[0] for r in conn.execute("SELECT name FROM schema_migrations")}
        try:
            row = conn.execute(
                "SELECT version FROM program_versions ORDER BY last_opened_at DESC LIMIT 1"
            ).fetchone()
        except sqlite3.Error:
            row = None
        return applied, (str(row[0]) if row else None)
    finally:
        conn.close()


def prepare_database(db: Path, version: str, now: datetime) -> Path | None:
    """Antes de abrir o banco: confere a versão e copia o banco se for haver atualização.

    Returns:
        A cópia feita antes da atualização, ou ``None`` se não havia o que atualizar.

    Raises:
        DatabaseNewerError: o banco tem migrações que esta versão não conhece (alguém
            voltou para uma versão anterior). Nada é alterado.
    """
    if not db.is_file():
        return None
    try:
        applied, last_version = _applied(db)
    except sqlite3.Error:
        return None  # banco sem tabela de migrações: o repositório cria do zero
    known = known_migrations()
    newer = sorted(applied - known)
    if newer:
        raise DatabaseNewerError(newer, last_version)
    if not applied or known <= applied:
        return None
    folder = db.parent / UPDATES_FOLDER
    folder.mkdir(parents=True, exist_ok=True)
    origin = last_version or "anterior"
    stamp = f"{now.astimezone(UTC):%Y%m%d-%H%M%S}"
    stem = f"qa-antes-da-{safe_part(version)}-de-{safe_part(origin)}-{stamp}"
    target = folder / f"{stem}.sqlite3"
    partial = target.with_name(target.name + ".part")
    source = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()
    partial.replace(target)
    copies = sorted(folder.glob("qa-antes-da-*.sqlite3"), key=lambda p: p.stat().st_mtime)
    for old in copies[:-KEEP_UPDATES]:
        old.unlink(missing_ok=True)
    return target


def update_copies(db: Path) -> list[Path]:
    """Cópias de antes de atualizações que esta versão consegue abrir, mais nova primeiro."""
    folder = db.parent / UPDATES_FOLDER
    if not folder.is_dir():
        return []
    usable = [p for p in folder.glob("qa-antes-da-*.sqlite3") if not check_backup(p)]
    return sorted(usable, key=lambda p: p.stat().st_mtime, reverse=True)


def restore_before_update(db: Path, now: datetime) -> tuple[Path, Path | None]:
    """Volta o banco para a cópia de antes da atualização mais recente que esta versão abre.

    O banco atual (da versão mais nova) não é apagado: fica ao lado, para voltar a ele
    quando a versão nova for reinstalada.

    Returns:
        ``(cópia restaurada, onde ficou o banco da versão mais nova)``.

    Raises:
        BackupError: não há cópia que esta versão consiga abrir.
    """
    copies = update_copies(db)
    if not copies:
        raise BackupError(
            "não há cópia de antes da atualização que esta versão consiga abrir; "
            "use qa backup list --all"
        )
    previous = restore_backup(copies[0], db, now)
    return copies[0], previous
