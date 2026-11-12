"""Porta ``Repository`` em SQLite, com migrações em SQL puro (ADR-0005)."""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
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
    source: str = "upload"
    stage: str | None = None
    queue: Mapping[str, Any] | None = None
    """Processos prontos e os que faltam (liberação por processo)."""

    def status_json(self) -> dict[str, Any]:
        """Formato de ``batch-status.schema.json``."""
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "status": self.status,
            "progress": {"done": self.done, "total": self.total},
            "created_at": self.created_at,
        }
        data["source"] = self.source
        if self.stage is not None and self.status in {"queued", "processing"}:
            data["stage"] = self.stage
        if self.error:
            data["error"] = self.error
        if self.summary is not None:
            data["summary"] = dict(self.summary)
        if self.queue is not None and self.status in {"queued", "processing"}:
            data["documents"] = dict(self.queue)
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
        """Fecha a conexão, esperando quem a está usando.

        Fechar no meio de uma consulta de outra thread (trabalho de fundo ainda rodando
        ao fechar o programa) derruba o processo no Windows. Depois de fechado, cada
        operação levanta ``sqlite3.ProgrammingError``, que o trabalho de fundo trata.
        """
        with self._lock:
            self._conn.close()

    def _one(self, sql: str, params: tuple[Any, ...] = ()) -> sqlite3.Row | None:
        # A conexão é compartilhada entre as threads da API: toda leitura passa pelo lock.
        with self._lock:
            row: sqlite3.Row | None = self._conn.execute(sql, params).fetchone()
            return row

    def _all(self, sql: str, params: tuple[Any, ...] = ()) -> list[sqlite3.Row]:
        with self._lock:
            return list(self._conn.execute(sql, params).fetchall())

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
        self,
        batch_id: str,
        name: str,
        profile_id: str,
        root: Path,
        created_at: str,
        source: str = "upload",
    ) -> None:
        """Registra um lote na fila."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO batches (id, name, profile_id, status, created_at, root, source) "
                "VALUES (?, ?, ?, 'queued', ?, ?, ?)",
                (batch_id, name, profile_id, created_at, str(root), source),
            )

    def set_stage(self, batch_id: str, stage: str | None) -> None:
        """Etapa do lote antes e durante a análise."""
        with self._tx() as c:
            c.execute("UPDATE batches SET stage = ? WHERE id = ?", (stage, batch_id))

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

    @contextmanager
    def locked(self) -> Iterator[None]:
        """Segura o banco para ler, mesclar e gravar sem outra thread no meio."""
        with self._lock:
            yield

    def save_report(
        self,
        batch_id: str,
        report: Mapping[str, Any],
        *,
        final: bool = True,
        queue: Mapping[str, Any] | None = None,
    ) -> None:
        """Grava o resultado da análise: relatório, páginas e sinalizações.

        Args:
            batch_id: lote.
            report: relatório no formato de ``analysis.schema.json``.
            final: passada final (o lote fica ``analyzed``); falso no relatório parcial
                da liberação por processo, que mantém o lote em análise.
            queue: processos prontos e os que faltam.
        """
        body = {k: v for k, v in report.items() if k != "findings"}
        summary = report["batch"]["summary"]
        queue_json = json.dumps(queue, ensure_ascii=False) if queue is not None else None
        with self._tx() as c:
            if final:
                c.execute(
                    "UPDATE batches SET status = 'analyzed', done = total, report_json = ?, "
                    "summary_json = ?, stage = NULL, queue_json = ? WHERE id = ?",
                    (
                        json.dumps(body, ensure_ascii=False),
                        json.dumps(summary),
                        queue_json,
                        batch_id,
                    ),
                )
            else:
                c.execute(
                    "UPDATE batches SET report_json = ?, summary_json = ?, queue_json = ? "
                    "WHERE id = ?",
                    (
                        json.dumps(body, ensure_ascii=False),
                        json.dumps(summary),
                        queue_json,
                        batch_id,
                    ),
                )
            c.executemany(
                "INSERT OR IGNORE INTO pages VALUES (?, ?, ?, ?, ?, ?)",
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
        row = self._one("SELECT * FROM batches WHERE id = ?", (batch_id,))
        return _batch(row) if row else None

    def list_batches(self) -> list[BatchRow]:
        """Todos os lotes, do mais recente ao mais antigo."""
        rows = self._all("SELECT * FROM batches ORDER BY created_at DESC, id")
        return [_batch(r) for r in rows]

    def get_report(self, batch_id: str) -> dict[str, Any] | None:
        """Relatório com as sinalizações e decisões vigentes."""
        row = self._one("SELECT report_json, summary_json FROM batches WHERE id = ?", (batch_id,))
        if row is None or row["report_json"] is None:
            return None
        report: dict[str, Any] = json.loads(row["report_json"])
        report["batch"]["summary"] = json.loads(row["summary_json"])
        report["findings"] = self.findings(batch_id)
        return report

    def findings(self, batch_id: str) -> list[dict[str, Any]]:
        """Sinalizações do lote, na ordem do relatório."""
        rows = self._all(
            "SELECT finding_json FROM findings WHERE batch_id = ? ORDER BY ord", (batch_id,)
        )
        return [json.loads(r[0]) for r in rows]

    def get_finding(self, finding_id: str) -> tuple[str, dict[str, Any]] | None:
        """``(batch_id, finding)`` pelo identificador."""
        row = self._one("SELECT batch_id, finding_json FROM findings WHERE id = ?", (finding_id,))
        return (row[0], json.loads(row[1])) if row else None

    def record_decisions(
        self,
        batch_id: str,
        findings: Sequence[Mapping[str, Any]],
        summary: Mapping[str, Any] | None,
    ) -> None:
        """Grava as decisões nas sinalizações e no histórico, numa transação."""
        with self._tx() as c:
            for finding in findings:
                decision = finding["decision"]
                c.execute(
                    "UPDATE findings SET finding_json = ? WHERE id = ?",
                    (json.dumps(finding, ensure_ascii=False), finding["id"]),
                )
                c.execute(
                    "INSERT INTO decisions (finding_id, batch_id, rule, action, reviewer,"
                    " decided_at, note, operation_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        finding["id"],
                        batch_id,
                        finding["rule"],
                        decision["action"],
                        decision["reviewer"],
                        decision["decided_at"],
                        decision.get("note"),
                        decision.get("operation_id"),
                    ),
                )
            if summary is not None:
                c.execute(
                    "UPDATE batches SET summary_json = ? WHERE id = ?",
                    (json.dumps(summary), batch_id),
                )

    def clear_decisions(
        self,
        batch_id: str,
        findings: Sequence[Mapping[str, Any]],
        reviewer: str,
        at: str,
        operation_id: str | None,
        summary: Mapping[str, Any] | None,
    ) -> None:
        """Grava as sinalizações sem decisão e registra ``undo`` no histórico."""
        with self._tx() as c:
            for finding in findings:
                c.execute(
                    "UPDATE findings SET finding_json = ? WHERE id = ?",
                    (json.dumps(finding, ensure_ascii=False), finding["id"]),
                )
                c.execute(
                    "INSERT INTO decisions (finding_id, batch_id, rule, action, reviewer,"
                    " decided_at, operation_id) VALUES (?, ?, ?, 'undo', ?, ?, ?)",
                    (finding["id"], batch_id, finding["rule"], reviewer, at, operation_id),
                )
            if summary is not None:
                c.execute(
                    "UPDATE batches SET summary_json = ? WHERE id = ?",
                    (json.dumps(summary), batch_id),
                )

    def set_summary(self, batch_id: str, summary: Mapping[str, Any]) -> None:
        """Atualiza o painel do lote."""
        with self._tx() as c:
            c.execute(
                "UPDATE batches SET summary_json = ? WHERE id = ?", (json.dumps(summary), batch_id)
            )

    # Operações de correção em lote ---------------------------------------------

    def create_operation(self, operation: Mapping[str, Any]) -> None:
        """Registra uma operação de correção em lote."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO operations (id, batch_id, scope_kind, scope_id, status, done, total,"
                " current, reviewer, started_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    operation["id"],
                    operation["batch_id"],
                    operation["scope"]["kind"],
                    operation["scope"]["id"],
                    operation["status"],
                    operation["progress"]["done"],
                    operation["progress"]["total"],
                    operation["progress"]["current"],
                    operation["reviewer"],
                    operation["started_at"],
                ),
            )

    def update_operation(self, operation_id: str, **fields: Any) -> None:
        """Atualiza campos da operação; ``result`` e ``undo`` são gravados como JSON."""
        columns = {
            "status",
            "done",
            "total",
            "current",
            "finished_at",
            "saved_at",
            "error",
        }
        sets: list[str] = []
        values: list[Any] = []
        for key, value in fields.items():
            if key in ("result", "undo"):
                sets.append(f"{key}_json = ?")
                values.append(json.dumps(value, ensure_ascii=False))
            elif key in columns:
                sets.append(f"{key} = ?")
                values.append(value)
            else:
                raise ValueError(f"campo de operação desconhecido: {key}")
        if not sets:
            return
        with self._tx() as c:
            c.execute(
                f"UPDATE operations SET {', '.join(sets)} WHERE id = ?",
                (*values, operation_id),
            )

    def get_operation(self, operation_id: str) -> dict[str, Any] | None:
        """Operação no formato de ``bulk-correction.schema.json``."""
        row = self._one("SELECT * FROM operations WHERE id = ?", (operation_id,))
        return _operation(row) if row else None

    def list_operations(self, batch_id: str) -> list[dict[str, Any]]:
        """Operações do lote, da mais recente à mais antiga."""
        rows = self._all(
            "SELECT * FROM operations WHERE batch_id = ? ORDER BY started_at DESC, rowid DESC",
            (batch_id,),
        )
        return [_operation(r) for r in rows]

    def update_metadata(self, batch_id: str, document_id: str, fields: list[Any]) -> None:
        """Substitui os metadados de um documento no relatório."""
        with self._tx() as c:
            row = c.execute("SELECT report_json FROM batches WHERE id = ?", (batch_id,)).fetchone()
            body = json.loads(row[0])
            body["metadata"][document_id] = fields
            c.execute(
                "UPDATE batches SET report_json = ? WHERE id = ?",
                (json.dumps(body, ensure_ascii=False), batch_id),
            )

    def decision_stats(self) -> dict[str, dict[str, int]]:
        """Contagem de decisões por regra e ação (precisão real de cada detector)."""
        stats: dict[str, dict[str, int]] = {}
        for rule, action, count in self._all(
            "SELECT rule, action, COUNT(*) FROM decisions GROUP BY rule, action ORDER BY rule"
        ):
            stats.setdefault(rule, {})[action] = count
        return stats

    # Páginas ---------------------------------------------------------------

    def get_page(self, page_id: str) -> dict[str, Any] | None:
        """Página pelo identificador."""
        row = self._one("SELECT * FROM pages WHERE id = ?", (page_id,))
        return dict(row) if row else None

    def document_batch(self, document_id: str) -> str | None:
        """Lote de um documento."""
        row = self._one("SELECT batch_id FROM pages WHERE document_id = ? LIMIT 1", (document_id,))
        return str(row[0]) if row else None

    def set_numbering(
        self,
        page_id: str,
        batch_id: str,
        value: str,
        reviewer: str,
        at: str,
        model_value: str | None = None,
        model_state: str | None = None,
    ) -> None:
        """Grava a numeração digitada pelo revisor e o que o modelo tinha resolvido.

        O que o modelo tinha resolvido fica da primeira digitação: corrigir de novo a
        mesma página não apaga a comparação com o modelo.
        """
        with self._tx() as c:
            c.execute(
                "INSERT INTO numbering_overrides (page_id, batch_id, value, reviewer, decided_at,"
                " model_value, model_state) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(page_id) "
                "DO UPDATE SET value = excluded.value, reviewer = excluded.reviewer, "
                "decided_at = excluded.decided_at",
                (page_id, batch_id, value, reviewer, at, model_value, model_state),
            )

    def numbering_override_rows(self, batch_id: str) -> list[dict[str, Any]]:
        """Numerações digitadas com o que o modelo tinha resolvido (coleta do beta)."""
        rows = self._all(
            "SELECT page_id, value, reviewer, decided_at, model_value, model_state "
            "FROM numbering_overrides WHERE batch_id = ?",
            (batch_id,),
        )
        return [dict(r) for r in rows]

    # Coleta do beta --------------------------------------------------------------

    def put_feedback(self, row: Mapping[str, Any]) -> str | None:
        """Grava um exemplo (um por tipo e página); devolve o arquivo de imagem substituído."""
        with self._tx() as c:
            old = c.execute(
                "SELECT image_file FROM feedback WHERE kind = ? AND page_id = ?",
                (row["kind"], row["page_id"]),
            ).fetchone()
            c.execute(
                "INSERT INTO feedback (id, kind, batch_id, page_id, reviewer, created_at,"
                " expires_at, label_json, model_json, image_file)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(kind, page_id) DO UPDATE SET"
                " id = excluded.id, reviewer = excluded.reviewer,"
                " created_at = excluded.created_at, expires_at = excluded.expires_at,"
                " label_json = excluded.label_json, model_json = excluded.model_json,"
                " image_file = excluded.image_file",
                (
                    row["id"],
                    row["kind"],
                    row["batch_id"],
                    row["page_id"],
                    row["reviewer"],
                    row["created_at"],
                    row["expires_at"],
                    json.dumps(row["label"], ensure_ascii=False),
                    json.dumps(row["model"], ensure_ascii=False),
                    row.get("image_file"),
                ),
            )
        replaced = old[0] if old else None
        return replaced if replaced and replaced != row.get("image_file") else None

    def remove_feedback(self, kind: str, page_id: str) -> str | None:
        """Apaga o exemplo de uma página; devolve o arquivo de imagem dele."""
        with self._tx() as c:
            old = c.execute(
                "SELECT image_file FROM feedback WHERE kind = ? AND page_id = ?", (kind, page_id)
            ).fetchone()
            c.execute("DELETE FROM feedback WHERE kind = ? AND page_id = ?", (kind, page_id))
        return old[0] if old else None

    def feedback_rows(
        self, kind: str | None = None, since: str | None = None, until: str | None = None
    ) -> list[dict[str, Any]]:
        """Exemplos da coleta, do mais antigo ao mais novo."""
        sql = "SELECT * FROM feedback WHERE 1 = 1"
        params: list[Any] = []
        for clause, value in (
            ("kind = ?", kind),
            ("created_at >= ?", since),
            ("created_at < ?", until),
        ):
            if value is not None:
                sql += f" AND {clause}"
                params.append(value)
        rows = self._all(sql + " ORDER BY created_at, id", tuple(params))
        out = []
        for r in rows:
            item = dict(r)
            item["label"] = json.loads(item.pop("label_json"))
            item["model"] = json.loads(item.pop("model_json"))
            out.append(item)
        return out

    def purge_feedback(self, now_iso: str) -> list[str | None]:
        """Apaga os exemplos vencidos; devolve o arquivo de imagem de cada um (ou ``None``)."""
        with self._tx() as c:
            rows = c.execute(
                "SELECT image_file FROM feedback WHERE expires_at <= ?", (now_iso,)
            ).fetchall()
            c.execute("DELETE FROM feedback WHERE expires_at <= ?", (now_iso,))
        return [r[0] for r in rows]

    def add_box_report(self, report_id: str, report: Mapping[str, Any], pendencies: str) -> None:
        """Guarda uma versão do relatório de uma caixa."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO box_reports VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    report_id,
                    report["batch_id"],
                    report["box"],
                    report["version"],
                    report["concluded_at"],
                    report["state"],
                    pendencies,
                    json.dumps(report, ensure_ascii=False),
                ),
            )

    def box_reports(self, batch_id: str) -> list[dict[str, Any]]:
        """Versões dos relatórios por caixa do lote (``id``, ``pendencies``, ``report``)."""
        rows = self._all(
            "SELECT id, pendencies, report_json FROM box_reports WHERE batch_id = ?"
            " ORDER BY box, version",
            (batch_id,),
        )
        return [{"id": r[0], "pendencies": r[1], "report": json.loads(r[2])} for r in rows]

    def all_box_reports(self) -> list[tuple[str, dict[str, Any]]]:
        """Todas as versões de todos os lotes deste computador (para a Gestão sem pasta)."""
        rows = self._all("SELECT id, report_json FROM box_reports ORDER BY created_at")
        return [(str(r[0]), json.loads(r[1])) for r in rows]

    def get_box_report(self, report_id: str) -> dict[str, Any] | None:
        """Uma versão de um relatório por caixa."""
        row = self._one("SELECT report_json FROM box_reports WHERE id = ?", (report_id,))
        return json.loads(row[0]) if row else None

    def save_beta_metrics(self, batch_id: str, created_at: str, metrics: Mapping[str, Any]) -> None:
        """Guarda as contagens do lote para o relatório do beta (sobrevivem à retenção)."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO beta_metrics VALUES (?, ?, ?) ON CONFLICT(batch_id) DO UPDATE SET"
                " metrics_json = excluded.metrics_json",
                (batch_id, created_at, json.dumps(metrics, ensure_ascii=False)),
            )

    def beta_metrics(self) -> dict[str, dict[str, Any]]:
        """Contagens guardadas de lotes que já saíram pela retenção."""
        rows = self._all("SELECT batch_id, created_at, metrics_json FROM beta_metrics")
        return {r[0]: {"created_at": r[1], **json.loads(r[2])} for r in rows}

    def add_complement(self, row: Mapping[str, Any], page: Mapping[str, Any]) -> None:
        """Registra uma folha inserida e a página dela."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO pages VALUES (?, ?, ?, ?, ?, ?)",
                (
                    page["id"],
                    row["batch_id"],
                    page["document_id"],
                    page["source_file"],
                    page["page_in_file"],
                    page["dpi"],
                ),
            )
            c.execute(
                "INSERT INTO complements (page_id, batch_id, document_id, file, sha256, position,"
                " inserted_by, inserted_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    page["id"],
                    row["batch_id"],
                    page["document_id"],
                    row["file"],
                    page["sha256"],
                    row["position"],
                    row["reviewer"],
                    row["at"],
                ),
            )

    def remove_complement(self, page_id: str, reviewer: str, at: str) -> None:
        """Marca a folha inserida como removida (a auditoria fica)."""
        with self._tx() as c:
            c.execute(
                "UPDATE complements SET removed_by = ?, removed_at = ? WHERE page_id = ?",
                (reviewer, at, page_id),
            )
            c.execute("DELETE FROM numbering_overrides WHERE page_id = ?", (page_id,))
            c.execute("DELETE FROM pages WHERE id = ?", (page_id,))

    def complements(self, batch_id: str) -> list[dict[str, Any]]:
        """Folhas inseridas no lote (inclusive as removidas, para auditoria)."""
        rows = self._all(
            "SELECT * FROM complements WHERE batch_id = ? ORDER BY inserted_at", (batch_id,)
        )
        return [dict(r) for r in rows]

    def add_config_changes(
        self, at: str, who: str, scope: str, target: str, items: Sequence[tuple[str, Any, Any]]
    ) -> None:
        """Registra mudanças de configuração (chave, antes, depois)."""
        if not items:
            return
        with self._tx() as c:
            c.executemany(
                "INSERT INTO config_history (at, who, scope, target, key, before_json, after_json)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        at,
                        who,
                        scope,
                        target,
                        key,
                        json.dumps(before, ensure_ascii=False),
                        json.dumps(after, ensure_ascii=False),
                    )
                    for key, before, after in items
                ],
            )

    def config_history(self, limit: int = 200) -> list[dict[str, Any]]:
        """Mudanças de configuração, da mais nova para a mais antiga."""
        rows = self._all(
            "SELECT seq, at, who, scope, target, key, before_json, after_json FROM config_history"
            " ORDER BY seq DESC LIMIT ?",
            (limit,),
        )
        return [
            {
                "id": r[0],
                "at": r[1],
                "who": r[2],
                "scope": r[3],
                "target": r[4],
                "key": r[5],
                "before": json.loads(r[6]) if r[6] is not None else None,
                "after": json.loads(r[7]) if r[7] is not None else None,
            }
            for r in rows
        ]

    def record_program_version(self, version: str, at: str) -> None:
        """Registra que esta versão do programa abriu o banco."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO program_versions VALUES (?, ?, ?) ON CONFLICT(version) DO UPDATE"
                " SET last_opened_at = excluded.last_opened_at",
                (version, at, at),
            )

    # Trava por caixa ------------------------------------------------------

    def hold_box(self, batch_id: str, box: str, scope: str, at: str) -> None:
        """Registra a caixa como travada por este lote."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO box_locks (batch_id, box, scope, state, acquired_at, renewed_at)"
                " VALUES (?, ?, ?, 'held', ?, ?) ON CONFLICT(batch_id, box) DO UPDATE SET"
                " scope = excluded.scope, state = 'held', acquired_at = excluded.acquired_at,"
                " renewed_at = excluded.renewed_at, ended_at = NULL, holder_json = NULL",
                (batch_id, box, scope, at, at),
            )

    def update_box_hold(self, batch_id: str, box: str, **fields: Any) -> None:
        """Muda ``scope``, ``state``, ``renewed_at``, ``ended_at`` ou ``holder``."""
        columns = {"scope", "state", "renewed_at", "ended_at", "holder"}
        unknown = set(fields) - columns
        if unknown:
            raise ValueError(f"campos desconhecidos: {sorted(unknown)}")
        if "holder" in fields:
            holder = fields.pop("holder")
            fields["holder_json"] = (
                json.dumps(holder, ensure_ascii=False) if holder is not None else None
            )
        if not fields:
            return
        assignments = ", ".join(f"{name} = ?" for name in fields)
        with self._tx() as c:
            c.execute(
                f"UPDATE box_locks SET {assignments} WHERE batch_id = ? AND box = ?",
                (*fields.values(), batch_id, box),
            )

    def box_holds(
        self, batch_id: str | None = None, state: str | None = None
    ) -> list[dict[str, Any]]:
        """Caixas travadas por esta máquina, na ordem em que foram travadas."""
        where, params = [], []
        if batch_id is not None:
            where.append("batch_id = ?")
            params.append(batch_id)
        if state is not None:
            where.append("state = ?")
            params.append(state)
        sql = "SELECT * FROM box_locks"
        if where:
            sql += " WHERE " + " AND ".join(where)
        rows = self._all(sql + " ORDER BY acquired_at, rowid", tuple(params))
        out = []
        for r in rows:
            item = dict(r)
            raw = item.pop("holder_json")
            item["holder"] = json.loads(raw) if raw else None
            out.append(item)
        return out

    def add_box_lock_event(self, event: Mapping[str, Any]) -> None:
        """Acrescenta um fato ao histórico das travas."""
        previous = event.get("previous")
        with self._tx() as c:
            c.execute(
                "INSERT INTO box_lock_events (at, kind, batch_id, box, who, machine, scope,"
                " previous_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event["at"],
                    event["kind"],
                    event["batch_id"],
                    event["box"],
                    event["who"],
                    event["machine"],
                    event["scope"],
                    json.dumps(previous, ensure_ascii=False) if previous else None,
                ),
            )

    def box_lock_events(self, batch_id: str) -> list[dict[str, Any]]:
        """Fatos das travas de um lote, do mais antigo ao mais novo."""
        rows = self._all(
            "SELECT at, kind, box, who, machine, scope, previous_json FROM box_lock_events"
            " WHERE batch_id = ? ORDER BY seq",
            (batch_id,),
        )
        out = []
        for r in rows:
            item: dict[str, Any] = {
                "at": r[0],
                "kind": r[1],
                "box": r[2],
                "who": r[3],
                "machine": r[4],
                "scope": r[5],
            }
            if r[6]:
                item["previous"] = json.loads(r[6])
            out.append(item)
        return out

    def delete_box_holds(self, batch_id: str) -> None:
        """Esquece as travas de um lote apagado pela retenção (o histórico fica)."""
        with self._tx() as c:
            c.execute("DELETE FROM box_locks WHERE batch_id = ?", (batch_id,))

    def clear_numbering(self, page_id: str) -> None:
        """Desfaz a numeração digitada de uma página."""
        with self._tx() as c:
            c.execute("DELETE FROM numbering_overrides WHERE page_id = ?", (page_id,))

    def set_manual_order(
        self,
        document_id: str,
        batch_id: str,
        page_ids: Sequence[str] | None,
        reviewer: str,
        at: str,
    ) -> None:
        """Grava (ou, com ``None``, desfaz) a ordem escolhida pelo revisor."""
        with self._tx() as c:
            if page_ids is None:
                c.execute("DELETE FROM manual_orders WHERE document_id = ?", (document_id,))
                return
            c.execute(
                "INSERT INTO manual_orders VALUES (?, ?, ?, ?, ?) ON CONFLICT(document_id) "
                "DO UPDATE SET page_ids = excluded.page_ids, reviewer = excluded.reviewer, "
                "decided_at = excluded.decided_at",
                (document_id, batch_id, json.dumps(list(page_ids)), reviewer, at),
            )

    def manual_orders(self, batch_id: str) -> dict[str, dict[str, Any]]:
        """Ordens escolhidas pelo revisor, por documento (páginas, revisor e horário)."""
        rows = self._all(
            "SELECT document_id, page_ids, reviewer, decided_at FROM manual_orders "
            "WHERE batch_id = ?",
            (batch_id,),
        )
        return {
            r[0]: {"page_ids": list(json.loads(r[1])), "reviewer": r[2], "decided_at": r[3]}
            for r in rows
        }

    def numbering_overrides(self, batch_id: str) -> dict[str, str]:
        """Numerações digitadas pelo revisor, por página."""
        rows = self._all(
            "SELECT page_id, value FROM numbering_overrides WHERE batch_id = ?", (batch_id,)
        )
        return {r[0]: r[1] for r in rows}

    # Retenção ---------------------------------------------------------------

    def batches_before(self, cutoff_iso: str) -> list[str]:
        """Lotes criados antes de ``cutoff_iso`` (os que a retenção vai apagar)."""
        rows = self._all("SELECT id FROM batches WHERE created_at < ?", (cutoff_iso,))
        return [str(r[0]) for r in rows]

    def purge_before(self, cutoff_iso: str) -> list[str]:
        """Apaga do banco os lotes criados antes de ``cutoff_iso``.

        Returns:
            Os identificadores apagados, para a entrada remover as pastas de trabalho.
            A pasta de origem nunca é devolvida: num lote local ela é o original.
        """
        with self._tx() as c:
            rows = c.execute(
                "SELECT id FROM batches WHERE created_at < ?", (cutoff_iso,)
            ).fetchall()
            c.execute("DELETE FROM batches WHERE created_at < ?", (cutoff_iso,))
        return [str(r[0]) for r in rows]

    def add_diagnostic(self, record: Mapping[str, Any]) -> None:
        """Grava um registro de diagnóstico (repetido pelo mesmo ``id`` é ignorado)."""
        with self._tx() as c:
            c.execute(
                "INSERT OR IGNORE INTO diagnostics (id, signature, at, record_json) "
                "VALUES (?, ?, ?, ?)",
                (
                    record["id"],
                    record["signature"],
                    record["at"],
                    json.dumps(record, ensure_ascii=False),
                ),
            )

    def diagnostics(self, since_iso: str | None = None) -> list[dict[str, Any]]:
        """Registros de diagnóstico, do mais antigo ao mais novo."""
        if since_iso:
            rows = self._all(
                "SELECT record_json FROM diagnostics WHERE at >= ? ORDER BY at", (since_iso,)
            )
        else:
            rows = self._all("SELECT record_json FROM diagnostics ORDER BY at")
        return [json.loads(r[0]) for r in rows]

    def resolve_diagnostic(self, signature: str, by: str, at: str) -> None:
        """Marca um grupo de erros como resolvido."""
        with self._tx() as c:
            c.execute(
                "INSERT INTO diagnostic_resolutions VALUES (?, ?, ?) ON CONFLICT(signature) "
                "DO UPDATE SET resolved_at = excluded.resolved_at, "
                "resolved_by = excluded.resolved_by",
                (signature, at, by),
            )

    def diagnostic_resolutions(self) -> dict[str, dict[str, Any]]:
        """Resolução por assinatura."""
        rows = self._all("SELECT signature, resolved_at, resolved_by FROM diagnostic_resolutions")
        return {r[0]: {"resolved_at": r[1], "resolved_by": r[2]} for r in rows}

    def add_findings(self, batch_id: str, findings: Sequence[Mapping[str, Any]]) -> None:
        """Acrescenta sinalizações no fim do relatório."""
        with self._tx() as c:
            row = c.execute(
                "SELECT COALESCE(MAX(ord), -1) FROM findings WHERE batch_id = ?", (batch_id,)
            ).fetchone()
            start = int(row[0]) + 1
            c.executemany(
                "INSERT INTO findings VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        f["id"],
                        batch_id,
                        start + i,
                        f["rule"],
                        f["severity"],
                        f["target"]["kind"],
                        f["target"]["id"],
                        json.dumps(f, ensure_ascii=False),
                    )
                    for i, f in enumerate(findings)
                ],
            )

    def update_finding(self, finding: Mapping[str, Any]) -> None:
        """Regrava uma sinalização sem mexer no histórico de decisões."""
        with self._tx() as c:
            c.execute(
                "UPDATE findings SET finding_json = ? WHERE id = ?",
                (json.dumps(finding, ensure_ascii=False), finding["id"]),
            )

    def decision_log(self, batch_id: str) -> list[dict[str, Any]]:
        """Histórico de decisões do lote, na ordem em que foram registradas."""
        rows = self._all(
            "SELECT d.finding_id, d.rule, d.action, d.reviewer, d.decided_at, d.note,"
            " d.operation_id FROM decisions d WHERE d.batch_id = ? ORDER BY d.seq",
            (batch_id,),
        )
        return [dict(r) for r in rows]


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
        source=row["source"],
        stage=row["stage"],
        queue=json.loads(row["queue_json"]) if row["queue_json"] else None,
    )


def _operation(row: sqlite3.Row) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": row["id"],
        "batch_id": row["batch_id"],
        "scope": {"kind": row["scope_kind"], "id": row["scope_id"]},
        "status": row["status"],
        "progress": {"done": row["done"], "total": row["total"], "current": row["current"]},
        "reviewer": row["reviewer"],
        "started_at": row["started_at"],
    }
    for key in ("finished_at", "saved_at", "error"):
        if row[key]:
            data[key] = row[key]
    if row["result_json"]:
        data["result"] = json.loads(row["result_json"])
    if row["undo_json"]:
        data["undo"] = json.loads(row["undo_json"])
    return data
