"""Caso de uso de lote local: abrir uma pasta, esperar ela parar de mudar e tirar o retrato.

O lote é lido no lugar e nunca alterado (ADR-0013). O retrato (tamanho, data e
SHA-256 de cada arquivo) é tirado antes da análise e conferido de novo antes de
gravar o lote corrigido: se algo mudou na pasta original, a gravação é recusada.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePath
from typing import Any

from qa_engine.adapters.images import SUPPORTED_SUFFIXES
from qa_engine.application.layout import RESERVED
from qa_engine.ports import BatchFolder, FileStamp

SNAPSHOT_FILE = "snapshot.json"
POLL_SECONDS = 1.0


class LocalBatchError(ValueError):
    """A pasta não pode ser aberta como lote."""

    status = 422


class NotAllowedError(LocalBatchError):
    """Pasta fora das raízes permitidas (``allowed_roots``)."""

    status = 403


class FolderNotFoundError(LocalBatchError):
    """A pasta não existe ou não está acessível."""

    status = 404


@dataclass(frozen=True, slots=True)
class LocalBatch:
    """Pasta aceita como lote."""

    root: Path
    """Caminho absoluto (no Windows, na forma estendida)."""
    name: str
    images: int


def open_local_batch(
    folder: BatchFolder,
    path: str,
    allowed_roots: Sequence[PurePath],
    is_within: Callable[[PurePath | str, tuple[PurePath, ...]], bool],
    name: str | None = None,
) -> LocalBatch:
    """Confere a pasta e a aceita como lote, sem copiar nada.

    Raises:
        NotAllowedError: fora de ``allowed_roots``.
        FolderNotFoundError: a pasta não existe.
        LocalBatchError: não é uma pasta ou não tem imagens.
    """
    try:
        root = folder.resolve(path)
    except FileNotFoundError as exc:
        raise FolderNotFoundError(str(exc)) from exc
    except NotADirectoryError as exc:
        raise LocalBatchError(str(exc)) from exc
    except OSError as exc:
        raise FolderNotFoundError(f"pasta inacessível: {exc.strerror or exc}") from exc
    if not is_within(root, tuple(allowed_roots)):
        raise NotAllowedError(
            "pasta fora das permitidas neste computador (allowed_roots); fale com a TI"
        )
    images = sum(
        1
        for rel in folder.listing(root)
        if PurePath(rel).suffix.lower() in SUPPORTED_SUFFIXES and PurePath(rel).name not in RESERVED
    )
    if images == 0:
        raise LocalBatchError("a pasta não tem imagens (TIFF, JPEG, PNG ou PDF)")
    return LocalBatch(root, name or PurePath(str(root).rstrip("\\/")).name or "lote", images)


def wait_until_stable(
    folder: BatchFolder,
    root: Path,
    seconds: float,
    *,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    poll: float = POLL_SECONDS,
    timeout: float | None = None,
) -> dict[str, FileStamp]:
    """Espera a pasta ficar ``seconds`` sem nenhum arquivo novo, apagado ou alterado.

    A digitalizadora pode ainda estar gravando o lote: analisar no meio daria
    falso "página faltando" e retrato errado.

    Raises:
        TimeoutError: a pasta não parou de mudar dentro de ``timeout``.
    """
    started = monotonic()
    last = folder.listing(root)
    stable_since = started
    while monotonic() - stable_since < seconds:
        if timeout is not None and monotonic() - started > timeout:
            raise TimeoutError("a pasta do lote continua mudando; tente de novo quando terminar")
        sleep(poll)
        current = folder.listing(root)
        if current != last:
            last = current
            stable_since = monotonic()
    return last


def take_snapshot(folder: BatchFolder, root: Path) -> dict[str, Any]:
    """Retrato da pasta: tamanho, data e SHA-256 de cada arquivo."""
    files: dict[str, Any] = {}
    for rel, stamp in folder.listing(root).items():
        files[rel] = {
            "size": stamp.size,
            "mtime_ns": stamp.mtime_ns,
            "sha256": folder.sha256(root / rel),
        }
    return {"version": 1, "files": files}


def compare_snapshot(folder: BatchFolder, root: Path, snapshot: Mapping[str, Any]) -> list[str]:
    """O que mudou na pasta desde o retrato (lista vazia = nada).

    Arquivo com o mesmo tamanho e data é considerado igual; senão o SHA-256 decide
    (copiar a pasta para outro lugar muda a data, não o conteúdo).
    """
    before: Mapping[str, Any] = snapshot.get("files", {})
    now = folder.listing(root)
    changes = [f"arquivo novo: {rel}" for rel in sorted(set(now) - set(before))]
    changes += [f"arquivo removido: {rel}" for rel in sorted(set(before) - set(now))]
    for rel in sorted(set(before) & set(now)):
        old, stamp = before[rel], now[rel]
        if stamp.size == old["size"] and stamp.mtime_ns == old["mtime_ns"]:
            continue
        if stamp.size != old["size"] or folder.sha256(root / rel) != old["sha256"]:
            changes.append(f"arquivo alterado: {rel}")
    return changes
