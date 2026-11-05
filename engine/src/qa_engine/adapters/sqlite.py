"""Porta ``Repository`` em SQLite, com migrações em SQL puro (ADR-0005)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class BatchRow:
    """Linha da tabela ``batches``."""

    id: str
    name: str
    profile_id: str
    status: str
    done: int
    total: int
    created_at: str
    root: Path
    error: str | None
    summary: Mapping[str, Any] | None

    def status_json(self) -> dict[str, Any]:
        """Formato de ``batch-status.schema.json``."""
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": {"done": self.done, "total": self.total},
            "created_at": self.created_at,
        }
        if self.error:
            data["error"] = self.error
        if self.summary is not None:
            data["summary"] = dict(self.summary)
        return data


class SqliteRepository:
    """Armazenamento de lotes, sinalizações e decisões num único arquivo."""

    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()
        self._migrate()

    def close(self) -> None:
        """Fecha a conexão."""
        self._conn.close()

    @contextmanager
    def _tx(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._conn.execute("BEGIN")
            try:
                yield self._conn
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
            self._conn.execute("COMMIT")

    def _migrate(self) -> None:
        with self._lock:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY)"
            )
            applied = {r[0] for r in self._conn.execute("SELECT name FROM schema_migrations")}
            folder = resources.files("qa_engine.adapters") / "migrations"
            for item in sorted(folder.iterdir(), key=lambda p: p.name):
                if not item.name.endswith(".sql") or item.name in applied:
                    continue
                self._conn.executescript(
                    "BEGIN;"
                    + item.read_text("utf-8")
                    + f"\nINSERT INTO schema_migrations VALUES ('{item.name}');COMMIT;"
                )

    # Lotes ---------------------------------------------------------------

    def create_batch(
        self, batch_id: str, name: str, profile_id: str, root: Path, created_at: str
    ) -> None:
        """Registra um lote na fila."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO batches (id, name, profile_id, status, created_at, root) "
                "VALUES (?, ?, ?, 'queued', ?, ?)",
                (batch_id, name, profile_id, created_at, str(root)),
            )

    def set_progress(self, batch_id: str, done: int, total: int) -> None:
        """Atualiza o progresso e marca o lote como em processamento."""
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET status = 'processing', done = ?, total = ? WHERE id = ?",
                (done, total, batch_id),
            )

    def fail(self, batch_id: str, error: str) -> None:
        """Marca o lote como falho."""
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET status = 'failed', error = ? WHERE id = ?", (error, batch_id)
            )

    def save_report(self, batch_id: str, report: Mapping[str, Any]) -> None:
        """Grava o resultado da análise: relatório, páginas e sinalizações."""
        body = {k: v for k, v in report.items() if k != "findings"}
        summary = report["batch"]["summary"]
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET status = 'analyzed', done = total, report_json = ?, "
                "summary_json = ? WHERE id = ?",
                (json.dumps(body, ensure_ascii=False), json.dumps(summary), batch_id),
            )
            c.executemany(
                "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
                [
                    (
                        p["id"],
                        batch_id,
                        p["document_id"],
                        p["source_file"],
                        p["page_in_file"],
                        p["dpi"],
                    )
                    for p in report["pages"]
                ],
            )
            self._replace_findings(c, batch_id, report["findings"])

    def _replace_findings(
        self, c: sqlite3.Connection, batch_id: str, findings: list[Mapping[str, Any]]
    ) -> None:
        c.execute("DELETE FROM findings WHERE batch_id = ?", (batch_id,))
        c.executemany(
            "INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f["id"],
                    batch_id,
                    i,
                    f["rule"],
                    f["severity"],
                    f["target"]["kind"],
                    f["target"]["id"],
                    json.dumps(f, ensure_ascii=False),
                )
                for i, f in enumerate(findings)
            ],
        )

    def replace_report(self, batch_id: str, report: Mapping[str, Any]) -> None:
        """Substitui relatório e sinalizações (depois de corrigir a numeração)."""
        body = {k: v for k, v in report.items() if k != "findings"}
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET report_json = ?, summary_json = ? WHERE id = ?",
                (
                    json.dumps(body, ensure_ascii=False),
                    json.dumps(report["batch"]["summary"]),
                    batch_id,
                ),
            )
            self._replace_findings(c, batch_id, list(report["findings"]))

    def get_batch(self, batch_id: str) -> BatchRow | None:
        """Lote pelo identificador."""
        row = self._conn.execute("SELECT * FROM batches WHERE id = ?", (batch_id,)).fetchone()
        return _batch(row) if row else None

    def list_batches(self) -> list[BatchRow]:
        """Todos os lotes, do mais recente ao mais antigo."""
        rows = self._conn.execute("SELECT * FROM batches ORDER BY created_at DESC, id").fetchall()
        return [_batch(r) for r in rows]

    def get_report(self, batch_id: str) -> dict[str, Any] | None:
        """Relatório com as sinalizações e decisões vigentes."""
        row = self._conn.execute(
            "SELECT report_json, summary_json FROM batches WHERE id = ?", (batch_id,)
        ).fetchone()
        if row is None or row["report_json"] is None:
            return None
        report: dict[str, Any] = json.loads(row["report_json"])
        report["batch"]["summary"] = json.loads(row["summary_json"])
        report["findings"] = self.findings(batch_id)
        return report

    def findings(self, batch_id: str) -> list[dict[str, Any]]:
        """Sinalizações do lote, na ordem do relatório."""
        rows = self._conn.execute(
            "SELECT finding_json FROM findings WHERE batch_id = ? ORDER BY ord", (batch_id,)
        ).fetchall()
        return [json.loads(r[0]) for r in rows]

    def get_finding(self, finding_id: str) -> tuple[str, dict[str, Any]] | None:
        """``(batch_id, finding)`` pelo identificador."""
        row = self._conn.execute(
            "SELECT batch_id, finding_json FROM findings WHERE id = ?", (finding_id,)
        ).fetchone()
        return (row[0], json.loads(row[1])) if row else None

    def record_decision(
        self, batch_id: str, finding: Mapping[str, Any], summary: Mapping[str, Any]
    ) -> None:
        """Grava a decisão na sinalização, no histórico e atualiza o painel do lote."""
        decision = finding["decision"]
        with self._tx() as c:
            c.execute(
                "UPDATE findings SET finding_json = ? WHERE id = ?",
                (json.dumps(finding, ensure_ascii=False), finding["id"]),
            )
            c.execute(
                "INSERT INTO decisions (finding_id, batch_id, rule, action, reviewer, decided_at,"
                " note) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    finding["id"],
                    batch_id,
                    finding["rule"],
                    decision["action"],
                    decision["reviewer"],
                    decision["decided_at"],
                    decision.get("note"),
                ),
            )
            c.execute(
                "UPDATE batches SET summary_json = ? WHERE id = ?",
                (json.dumps(summary), batch_id),
            )

    def decision_stats(self) -> dict[str, dict[str, int]]:
        """Contagem de decisões por regra e ação (precisão real de cada detector)."""
        stats: dict[str, dict[str, int]] = {}
        for rule, action, count in self._conn.execute(
            "SELECT rule, action, COUNT(*) FROM decisions GROUP BY rule, action ORDER BY rule"
        ):
            stats.setdefault(rule, {})[action] = count
        return stats

    # Páginas ---------------------------------------------------------------

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        """Página pelo identificador."""
        row = self._conn.execute("SELECT * FROM pages WHERE id = ?", (page_id,)).fetchone()
        return dict(row) if row else None

    def document_batch(self, document_id: str) -> str | None:
        """Lote de um documento."""
        row = self._conn.execute(
            "SELECT batch_id FROM pages WHERE document_id = ? LIMIT 1", (document_id,)
        ).fetchone()
        return str(row[0]) if row else None

    def set_numbering(
        self, page_id: str, batch_id: str, value: str, reviewer: str, at: str
    ) -> None:
        """Grava a numeração digitada pelo revisor."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO numbering_overrides VALUES (?, ?, ?, ?, ?) ON CONFLICT(page_id) "
                "DO UPDATE SET value = excluded.value, reviewer = excluded.reviewer, "
                "decided_at = excluded.decided_at",
                (page_id, batch_id, value, reviewer, at),
            )

    def numbering_overrides(self, batch_id: str) -> dict[str, str]:
        """Numerações digitadas pelo revisor, por página."""
        rows = self._conn.execute(
            "SELECT page_id, value FROM numbering_overrides WHERE batch_id = ?", (batch_id,)
        ).fetchall()
        return {r[0]: r[1] for r in rows}

    # Retenção ---------------------------------------------------------------

    def purge_before(self, cutoff_iso: str) -> list[Path]:
        """Apaga lotes criados antes de ``cutoff_iso``; devolve as pastas para remover."""
        with self._tx() as c:
            rows = c.execute(
                "SELECT root FROM batches WHERE created_at < ?", (cutoff_iso,)
            ).fetchall()
            c.execute("DELETE FROM batches WHERE created_at < ?", (cutoff_iso,))
        return [Path(r[0]) for r in rows]


def _batch(row: sqlite3.Row) -> BatchRow:
    return BatchRow(
        id=row["id"],
        name=row["name"],
        profile_id=row["profile_id"],
        status=row["status"],
        done=row["done"],
        total=row["total"],
        created_at=row["created_at"],
        root=Path(row["root"]),
        error=row["error"],
        summary=json.loads(row["summary_json"]) if row["summary_json"] else None,
    )
