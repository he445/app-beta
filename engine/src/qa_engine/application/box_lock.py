"""Trava por caixa: dois conferentes não conferem a mesma caixa em máquinas diferentes.

Especificação: ``docs/especificacoes/trava-por-caixa.md``. A pasta original é só
leitura, então a trava fica na pasta compartilhada de relatórios: um arquivo por caixa
com conferente, máquina e horário, renovado a cada minuto enquanto a caixa está aberta
(da abertura do lote até a caixa ser concluída). Trava sem renovação há mais de dez
minutos é abandonada e pode ser assumida, com registro de quem assumiu. Sem pasta
compartilhada (ou com ela fora do ar), a trava vale só neste computador.
"""

from __future__ import annotations

import contextlib
import logging
from collections.abc import Callable, Iterable, Mapping
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import PurePosixPath
from typing import Any, Protocol

from qa_engine.adapters.images import SUPPORTED_SUFFIXES
from qa_engine.application.layout import RESERVED
from qa_engine.ports import BoxLock, BoxLockStore

log = logging.getLogger("qa_engine.box_lock")

ABANDONED_AFTER = timedelta(minutes=10)
"""Sem renovação por mais que isso, a trava é considerada abandonada."""
RENEW_SECONDS = 60.0
"""Intervalo de renovação das travas da própria máquina."""


class BoxLockedError(Exception):
    """Alguma caixa do lote está travada por outra pessoa ou máquina."""

    status = 409

    def __init__(self, locks: list[dict[str, Any]]) -> None:
        self.locks = locks
        super().__init__(" ".join(lock["message"] for lock in locks))

    @property
    def can_take_over(self) -> bool:
        """Todas as travas no caminho estão abandonadas (podem ser assumidas)."""
        return all(lock["abandoned"] for lock in self.locks)


class HoldRepository(Protocol):
    """Onde a máquina guarda as caixas que travou e o histórico das travas."""

    def hold_box(self, batch_id: str, box: str, scope: str, at: str) -> None:
        """Registra a caixa como travada por este lote."""
        ...

    def update_box_hold(self, batch_id: str, box: str, **fields: Any) -> None:
        """Muda ``scope``, ``state``, ``renewed_at``, ``ended_at`` ou ``holder``."""
        ...

    def box_holds(
        self, batch_id: str | None = None, state: str | None = None
    ) -> list[dict[str, Any]]:
        """Caixas travadas por esta máquina."""
        ...

    def add_box_lock_event(self, event: Mapping[str, Any]) -> None:
        """Acrescenta um fato ao histórico."""
        ...

    def box_lock_events(self, batch_id: str) -> list[dict[str, Any]]:
        """Fatos das travas de um lote, do mais antigo ao mais novo."""
        ...


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso(when: datetime) -> str:
    return when.isoformat(timespec="seconds")


def _clock(value: str) -> str:
    when = _parse(value).astimezone()
    return when.strftime("%H:%M de %d/%m/%Y")


def is_abandoned(lock: BoxLock, now: datetime) -> bool:
    """Sem renovação há mais de :data:`ABANDONED_AFTER`."""
    return now - _parse(lock.renewed_at) > ABANDONED_AFTER


def box_label(box: str) -> str:
    """``Caixa 0412`` (sem repetir a palavra quando a pasta já se chama assim)."""
    return box if box.casefold().startswith("caixa") else f"Caixa {box}"


def lock_message(lock: BoxLock, abandoned: bool) -> str:
    """Frase para a tela: quem, onde e desde quando."""
    who = f"por {lock.reviewer}, na máquina {lock.machine}, desde {_clock(lock.since)}"
    if abandoned:
        return (
            f"{box_label(lock.box)} estava em conferência {who}, sem sinal desde "
            f"{_clock(lock.renewed_at)}: a trava foi abandonada e pode ser assumida."
        )
    return f"{box_label(lock.box)} em conferência {who}."


def lock_view(lock: BoxLock, now: datetime) -> dict[str, Any]:
    """Trava no formato de ``box-lock.schema.json``."""
    abandoned = is_abandoned(lock, now)
    data: dict[str, Any] = {
        "box": lock.box,
        "reviewer": lock.reviewer,
        "machine": lock.machine,
        "since": lock.since,
        "renewed_at": lock.renewed_at,
        "abandoned": abandoned,
        "message": lock_message(lock, abandoned),
    }
    if lock.taken_over_from:
        data["taken_over_from"] = dict(lock.taken_over_from)
    return data


def boxes_of_files(
    rels: Iterable[str], batch_name: str, is_multipage: Callable[[str], bool]
) -> list[str]:
    """Caixas de um lote pela lista de arquivos, antes da análise.

    Mesma regra do relatório por caixa (a primeira pasta do documento) aplicada ao
    agrupamento do layout do lote: imagem de página única a dois níveis forma um
    documento com o nome da pasta, que fica direto no lote (caixa = lote); PDF ou TIFF
    multipágina a dois níveis é um documento dentro da pasta (caixa = pasta).
    """
    found: list[str] = []
    for rel in rels:
        path = PurePosixPath(rel)
        if (
            path.name in RESERVED
            or path.suffix.lower() not in SUPPORTED_SUFFIXES
            or any(part.startswith(".") for part in path.parts)
        ):
            continue
        parts = path.parts
        inside = len(parts) == 2 and (path.suffix.lower() == ".pdf" or is_multipage(rel))
        box = parts[0] if len(parts) >= 3 or inside else batch_name
        if box not in found:
            found.append(box)
    return found


class BoxLocks:
    """Trava, renova e solta as caixas abertas nesta máquina."""

    def __init__(
        self,
        shared: BoxLockStore | None,
        local: BoxLockStore,
        repo: HoldRepository,
        *,
        machine: str,
        reviewer: str,
        program_version: str,
        now: Callable[[], datetime],
    ) -> None:
        self.shared = shared
        self.local = local
        self.repo = repo
        self.machine = machine
        self.reviewer = reviewer
        self.program_version = program_version
        self.now = now

    def own(self, lock: BoxLock) -> bool:
        """A trava é desta pessoa nesta máquina (abrir de novo a própria caixa é permitido)."""
        return (
            lock.machine.casefold() == self.machine.casefold()
            and lock.reviewer.casefold() == self.reviewer.casefold()
        )

    def _store(self, scope: str) -> BoxLockStore:
        return self.shared if scope == "shared" and self.shared is not None else self.local

    def _event(
        self,
        kind: str,
        batch_id: str,
        box: str,
        scope: str,
        previous: BoxLock | None = None,
        store: BoxLockStore | None = None,
    ) -> None:
        event: dict[str, Any] = {
            "at": _iso(self.now()),
            "kind": kind,
            "batch_id": batch_id,
            "box": box,
            "who": self.reviewer,
            "machine": self.machine,
            "scope": scope,
            "previous": _summary(previous) if previous else None,
        }
        self.repo.add_box_lock_event(event)
        if store is not None:
            try:
                store.log(event)
            except OSError as exc:
                log.warning("histórico de travas indisponível: %s", exc.strerror or exc)

    def acquire(self, batch_id: str, boxes: Iterable[str], take_over: bool = False) -> str:
        """Trava as caixas do lote; devolve onde a trava vale (``shared`` ou ``local``).

        Raises:
            BoxLockedError: caixa travada por outra pessoa ou máquina. Trava abandonada
                só é assumida com ``take_over``; trava viva nunca.
        """
        wanted = list(dict.fromkeys(boxes))
        now = self.now()
        scope, store, current = self._inspect(wanted)
        others = {box: lock for box, lock in current.items() if lock and not self.own(lock)}
        alive = [lock for lock in others.values() if not is_abandoned(lock, now)]
        if alive or (others and not take_over):
            raise BoxLockedError([lock_view(lock, now) for lock in others.values()])
        written: list[str] = []
        for box in wanted:
            lock = BoxLock(
                box=box,
                reviewer=self.reviewer,
                machine=self.machine,
                since=_iso(now),
                renewed_at=_iso(now),
                batch_id=batch_id,
                program_version=self.program_version,
            )
            previous = others.get(box)
            try:
                if previous is not None:
                    store.write(replace(lock, taken_over_from=_summary(previous)))
                elif not store.create(lock):
                    existing = store.read(box)
                    if existing is not None and not self.own(existing):
                        # Outra máquina criou a trava entre a leitura e a gravação.
                        self._undo(written, store)
                        raise BoxLockedError([lock_view(existing, now)])
                    store.write(lock)
            except OSError:
                self._undo(written, store)
                raise
            written.append(box)
            self.repo.hold_box(batch_id, box, scope, _iso(now))
            if previous is not None:
                self._event("taken_over", batch_id, box, scope, previous, store)
            else:
                self._event("acquired", batch_id, box, scope)
        return scope

    def _inspect(self, boxes: list[str]) -> tuple[str, BoxLockStore, dict[str, BoxLock | None]]:
        if self.shared is not None:
            try:
                return "shared", self.shared, {box: self.shared.read(box) for box in boxes}
            except OSError as exc:
                log.warning(
                    "pasta compartilhada de travas indisponível; a trava vale só neste "
                    "computador: %s",
                    exc.strerror or exc,
                )
        return "local", self.local, {box: self.local.read(box) for box in boxes}

    def _undo(self, boxes: list[str], store: BoxLockStore) -> None:
        for box in boxes:
            try:
                store.remove(box)
            except OSError:
                log.warning("não foi possível desfazer a trava da caixa %s", box)

    def ensure(self, batch_id: str, box: str) -> None:
        """Trava de novo uma caixa reaberta (folha inserida depois), se não estiver travada."""
        held = self.repo.box_holds(batch_id, "held")
        if any(item["box"] == box for item in held):
            return
        self.acquire(batch_id, [box])

    def renew(self) -> None:
        """Renova as travas desta máquina; perde as que outra máquina assumiu.

        Trava que só valia neste computador (pasta compartilhada fora do ar) passa para
        a pasta compartilhada quando ela volta; enquanto não volta, é renovada aqui.
        """
        now = _iso(self.now())
        for hold in self.repo.box_holds(state="held"):
            scope = hold["scope"]
            targets = ["shared", "local"] if scope == "local" and self.shared else [scope]
            for target in targets:
                try:
                    outcome = self._renew_one(hold, target, now)
                except OSError as exc:
                    log.warning("trava da caixa %s não renovada: %s", hold["box"], exc)
                    continue
                if outcome == "renewed" and target != scope:
                    with contextlib.suppress(OSError):
                        self.local.remove(hold["box"])
                break

    def _renew_one(self, hold: Mapping[str, Any], target: str, now: str) -> str:
        batch_id, box = hold["batch_id"], hold["box"]
        store = self._store(target)
        current = store.read(box)
        if current is None:
            lock = BoxLock(
                box=box,
                reviewer=self.reviewer,
                machine=self.machine,
                since=hold["acquired_at"],
                renewed_at=now,
                batch_id=batch_id,
                program_version=self.program_version,
            )
            if not store.create(lock):
                return "retry"  # alguém criou agora; decide na próxima renovação
        elif not self.own(current):
            self.repo.update_box_hold(
                batch_id, box, state="lost", ended_at=now, holder=lock_json_view(current)
            )
            self._event("lost", batch_id, box, target, current)
            return "lost"
        elif current.batch_id and current.batch_id != batch_id:
            # A mesma pessoa abriu a caixa de novo noutro lote: este lote solta.
            self.repo.update_box_hold(batch_id, box, state="released", ended_at=now)
            return "superseded"
        else:
            store.write(replace(current, renewed_at=now))
        self.repo.update_box_hold(batch_id, box, scope=target, renewed_at=now)
        return "renewed"

    def release(self, batch_id: str, boxes: Iterable[str] | None = None) -> None:
        """Solta as travas do lote (caixa concluída, lote apagado ou análise que falhou)."""
        only = set(boxes) if boxes is not None else None
        now = _iso(self.now())
        for hold in self.repo.box_holds(batch_id, "held"):
            box, scope = hold["box"], hold["scope"]
            if only is not None and box not in only:
                continue
            store = self._store(scope)
            try:
                current = store.read(box)
                if current is not None and self.own(current) and current.batch_id == batch_id:
                    store.remove(box)
            except OSError as exc:
                log.warning("não foi possível soltar a trava da caixa %s: %s", box, exc)
            self.repo.update_box_hold(batch_id, box, state="released", ended_at=now)
            self._event("released", batch_id, box, scope)

    def status(self, batch_id: str) -> dict[str, Any]:
        """Travas de um lote (``box-locks.schema.json``)."""
        boxes = []
        for hold in self.repo.box_holds(batch_id):
            item: dict[str, Any] = {
                "box": hold["box"],
                "state": hold["state"],
                "scope": hold["scope"],
                "acquired_at": hold["acquired_at"],
            }
            if hold.get("ended_at"):
                item["ended_at"] = hold["ended_at"]
            if hold.get("holder"):
                holder = _lock_from_view(hold["holder"])
                item["holder"] = lock_view(holder, self.now())
            boxes.append(item)
        return {
            "enabled": True,
            "shared_configured": self.shared is not None,
            "boxes": boxes,
            "events": self.repo.box_lock_events(batch_id),
        }


def _summary(lock: BoxLock) -> dict[str, Any]:
    return {
        "reviewer": lock.reviewer,
        "machine": lock.machine,
        "since": lock.since,
        "renewed_at": lock.renewed_at,
    }


def lock_json_view(lock: BoxLock) -> dict[str, Any]:
    """Trava guardada no banco (para mostrar quem assumiu a caixa)."""
    data = {**_summary(lock), "box": lock.box, "batch_id": lock.batch_id}
    if lock.taken_over_from:
        data["taken_over_from"] = dict(lock.taken_over_from)
    return data


def _lock_from_view(data: Mapping[str, Any]) -> BoxLock:
    return BoxLock(
        box=str(data["box"]),
        reviewer=str(data["reviewer"]),
        machine=str(data["machine"]),
        since=str(data["since"]),
        renewed_at=str(data["renewed_at"]),
        batch_id=str(data.get("batch_id", "")),
        taken_over_from=data.get("taken_over_from"),
    )
