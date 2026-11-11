"""Casos de uso de correção individual, em lote e do lote corrigido (ADR-0009).

Decisão individual, "Corrigir tudo", desfazer em lote, plano do lote corrigido
e "Salvar correções" (``docs/especificacoes/corrections.md``).

A entrada HTTP só traduz requisições para estes métodos.
"""

from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qa_engine.adapters.local_folder import display_path
from qa_engine.application.bulk import SkipCategory, plan_bulk, skip_entry
from qa_engine.application.contracts import validate
from qa_engine.application.corrected_batch import build_plan, manifest_csv, plan_totals, raster_dpi
from qa_engine.application.corrections import (
    IMAGE_ACTIONS,
    CorrectionNotApplicableError,
    active_chain,
    chain_key,
    current_version,
    refresh_page,
    render_chain,
)
from qa_engine.application.exports import decisions_csv, findings_csv
from qa_engine.application.profile import Profile
from qa_engine.application.review import decide, finding_from_json, recompute_summary
from qa_engine.application.serialize import iso
from qa_engine.detectors.base import Stats
from qa_engine.domain.model import CorrectionAction, DecisionAction, Finding
from qa_engine.ports import (
    Clock,
    CorrectedBatchWriter,
    ImageSource,
    LoadError,
    MetadataReader,
    PageVersionStore,
    ReviewStore,
)

CORRECTED_ZIP = "lote-corrigido.zip"
FINISHED = {"applied", "saved", "undone", "failed"}
UNDOABLE = {"applied", "saved", "failed"}


class NotFoundError(LookupError):
    """Lote, documento, página, sinalização ou operação inexistente."""


class ConflictError(ValueError):
    """A operação não pode ser feita no estado atual."""


class SourceChangedError(ConflictError):
    """Salvar recusado: a pasta original do lote mudou desde a análise."""

    def __init__(self, changes: Sequence[str]) -> None:
        self.changes = list(changes)
        shown = "; ".join(self.changes[:5])
        more = f" (e mais {len(self.changes) - 5})" if len(self.changes) > 5 else ""
        super().__init__(
            "A pasta original do lote mudou durante a revisão: "
            f"{shown}{more}. Abra o lote de novo para analisar a versão atual."
        )


class SaveBlockedError(ConflictError):
    """Salvar recusado: há página faltando sem decisão."""

    def __init__(self, blockers: Sequence[Mapping[str, Any]]) -> None:
        self.blockers = list(blockers)
        names = "; ".join(b["message"] for b in self.blockers)
        super().__init__(f"Há página faltando sem decisão. {names}")


@dataclass(frozen=True, slots=True)
class BatchContext:
    """O que os casos de uso precisam saber de um lote."""

    batch_id: str
    name: str
    root: Path
    """Pasta do lote original (nunca é alterada)."""
    profile: Profile
    baselines: Mapping[str, Mapping[str, Stats]]
    versions: PageVersionStore


class CorrectionService:
    """Casos de uso de correção sobre as portas de armazenamento e imagem."""

    def __init__(
        self,
        store: ReviewStore,
        images: ImageSource,
        metadata: MetadataReader,
        clock: Clock,
        engine_version: str,
    ) -> None:
        self.store = store
        self.images = images
        self.metadata = metadata
        self.clock = clock
        self.engine_version = engine_version

    # Apoio ---------------------------------------------------------------------

    def _report(self, ctx: BatchContext) -> dict[str, Any]:
        report = self.store.get_report(ctx.batch_id)
        if report is None:
            raise ConflictError("lote ainda não analisado")
        return report

    def _loader(
        self, ctx: BatchContext, page: Mapping[str, Any]
    ) -> Callable[[], NDArray[np.uint8]]:
        def load() -> NDArray[np.uint8]:
            return self.images.load_original(ctx.root / page["source_file"], page["page_in_file"])

        return load

    def _refresh(
        self,
        ctx: BatchContext,
        page: Mapping[str, Any],
        chain: Sequence[Finding],
        *,
        event: str,
        finding_ids: Sequence[str],
        reviewer: str,
        now: datetime,
        operation_id: str | None = None,
    ) -> dict[str, Any]:
        record = refresh_page(
            store=ctx.versions,
            page_id=page["id"],
            chain=chain,
            load_original=self._loader(ctx, page),
            dpi=raster_dpi(page),
            source_sha256=page["sha256"],
            profile=ctx.profile,
            baselines=ctx.baselines,
            now=now,
            event=event,
            finding_ids=finding_ids,
            reviewer=reviewer,
            operation_id=operation_id,
            station_id=page.get("station_id"),
        )
        return {
            "output": record.output,
            "output_sha256": record.output_sha256,
            "remaining_rules": list(record.remaining_rules),
        }

    def _final_image(
        self, ctx: BatchContext, page: Mapping[str, Any], findings: Sequence[Finding]
    ) -> NDArray[np.uint8] | None:
        """Versão corrigida mais recente da página, ou ``None`` se não há correção."""
        chain = active_chain(findings, page["id"])
        if not chain:
            return None
        name = current_version(ctx.versions, page["id"], chain)
        image = ctx.versions.load(name) if name else None
        return image if image is not None else render_chain(self._loader(ctx, page)(), chain)

    @staticmethod
    def _find(report: Mapping[str, Any], finding_id: str) -> tuple[int, dict[str, Any]]:
        for i, finding in enumerate(report["findings"]):
            if finding["id"] == finding_id:
                return i, finding
        raise NotFoundError("sinalização não encontrada")

    # Decisão individual ------------------------------------------------------------

    def decide(
        self,
        ctx: BatchContext,
        finding_id: str,
        action: DecisionAction,
        reviewer: str,
        note: str | None = None,
    ) -> dict[str, Any]:
        """Registra uma decisão; ``correct`` numa correção de imagem gera a cópia corrigida.

        Returns:
            ``{"finding", "summary"}`` e, quando uma cópia foi gravada, ``"applied"``.

        Raises:
            NotFoundError: sinalização inexistente.
            ConflictError: a página não pôde ser lida para aplicar a correção.
        """
        report = self._report(ctx)
        index, old = self._find(report, finding_id)
        now = self.clock.now()
        updated = decide(old, action, reviewer, now, note)
        applied = self._sync_page(
            ctx, report, index, updated, event="applied", reviewer=reviewer, now=now
        )
        report["findings"][index] = updated
        summary = recompute_summary(report, ctx.profile)
        self.store.record_decisions(ctx.batch_id, [updated], summary)
        response: dict[str, Any] = {"finding": updated, "summary": summary}
        if applied is not None and action is DecisionAction.CORRECT:
            response["applied"] = applied
        return response

    def undo(self, ctx: BatchContext, finding_id: str, reviewer: str) -> dict[str, Any]:
        """Desfaz a decisão de uma sinalização (Ctrl+Z) e recalcula a versão da página.

        Raises:
            NotFoundError: sinalização inexistente.
            ConflictError: a sinalização não tem decisão.
        """
        report = self._report(ctx)
        index, old = self._find(report, finding_id)
        if not old.get("decision"):
            raise ConflictError("a sinalização não tem decisão para desfazer")
        now = self.clock.now()
        updated = {k: v for k, v in old.items() if k != "decision"}
        self._sync_page(ctx, report, index, updated, event="undone", reviewer=reviewer, now=now)
        report["findings"][index] = updated
        summary = recompute_summary(report, ctx.profile)
        self.store.clear_decisions(ctx.batch_id, [updated], reviewer, iso(now), None, summary)
        return {"finding": updated, "summary": summary}

    def _sync_page(
        self,
        ctx: BatchContext,
        report: Mapping[str, Any],
        index: int,
        updated: Mapping[str, Any],
        *,
        event: str,
        reviewer: str,
        now: datetime,
    ) -> dict[str, Any] | None:
        """Regrava a versão da página se a decisão mudou a cadeia de correções."""
        if updated["target"]["kind"] != "page":
            return None
        page_id = updated["target"]["id"]
        before = [finding_from_json(f) for f in report["findings"]]
        after = list(before)
        after[index] = finding_from_json(updated)
        old_chain = chain_key(active_chain(before, page_id))
        new_chain = active_chain(after, page_id)
        if old_chain == chain_key(new_chain):
            return None
        page = next(p for p in report["pages"] if p["id"] == page_id)
        try:
            return self._refresh(
                ctx,
                page,
                new_chain,
                event=event,
                finding_ids=[updated["id"]],
                reviewer=reviewer,
                now=now,
            )
        except (LoadError, OSError, CorrectionNotApplicableError) as exc:
            raise ConflictError(f"não foi possível corrigir a página: {exc}") from exc

    # Rotação escolhida pelo revisor ------------------------------------------------

    def set_rotation(
        self, ctx: BatchContext, page_id: str, angle: int, reviewer: str
    ) -> dict[str, Any]:
        """Gira a página na cópia pelo ângulo escolhido (giro horário total: 0, 90, 180, 270).

        Vira sempre uma decisão auditada numa sinalização ``orientation``: a do modelo,
        se houver (a rotação proposta passa a ser a escolhida), ou uma nova, "rotação
        escolhida pelo revisor". Ângulo 0 aprova a sinalização existente (não girar).

        Raises:
            NotFoundError: página fora do lote.
            ConflictError: ângulo 0 sem sinalização de orientação na página.
        """
        report = self._report(ctx)
        page = next((p for p in report["pages"] if p["id"] == page_id), None)
        if page is None:
            raise NotFoundError("página não encontrada")
        mine = [
            f
            for f in report["findings"]
            if f["rule"] == "orientation" and f["target"] == {"kind": "page", "id": page_id}
        ]
        if angle == 0:
            if not mine:
                raise ConflictError("a página não está girada: nada a desfazer")
            return self.decide(
                ctx, mine[-1]["id"], DecisionAction.APPROVE, reviewer, "não girar (revisor)"
            )
        text = f"Girar {angle}° no sentido horário na cópia (escolhido pelo revisor)."
        if mine:
            finding = json.loads(json.dumps(mine[-1]))
            params = dict(finding["correction"].get("params", {}))
            params.pop("review", None)
            params.update({"angle_deg": angle, "manual": True})
            finding["correction"] = {**finding["correction"], "params": params, "description": text}
            finding.pop("decision", None)
            self.store.update_finding(finding)
        else:
            from qa_engine.detectors.registry import manifest
            from qa_engine.domain import ids

            finding = {
                "id": ids.finding_id(ctx.batch_id, page_id, "orientation", 0),
                "target": {"kind": "page", "id": page_id},
                "rule": "orientation",
                "rule_version": manifest("orientation").version,
                "severity": "medium",
                "measure": 1.0,
                "threshold": 0.0,
                "confidence": 1.0,
                "message": "Rotação escolhida pelo revisor.",
                "correction": {
                    "kind": "automatic",
                    "action": "rotate",
                    "description": text,
                    "params": {"angle_deg": angle, "manual": True},
                },
            }
            self.store.add_findings(ctx.batch_id, [finding])
        return self.decide(
            ctx, finding["id"], DecisionAction.CORRECT, reviewer, f"rotação de {angle}° (revisor)"
        )

    # Corrigir tudo -----------------------------------------------------------------

    def operations(self, batch_id: str) -> list[dict[str, Any]]:
        """Operações de correção em lote do lote."""
        return self.store.list_operations(batch_id)

    def operation(self, operation_id: str) -> dict[str, Any]:
        """Estado da operação; terminada, traz o painel atual do lote.

        Raises:
            NotFoundError: operação inexistente.
        """
        op = self.store.get_operation(operation_id)
        if op is None:
            raise NotFoundError("operação não encontrada")
        if op["status"] in FINISHED:
            report = self.store.get_report(op["batch_id"])
            if report is not None:
                op["summary"] = report["batch"]["summary"]
        return op

    def start_bulk(
        self, ctx: BatchContext, scope_kind: str, scope_id: str | None, reviewer: str
    ) -> dict[str, Any]:
        """Cria a operação "Corrigir tudo" na fila; ``run_bulk`` a executa.

        Raises:
            NotFoundError: documento fora do lote.
            ConflictError: já há uma operação em andamento no lote.
        """
        if any(op["status"] in {"queued", "running"} for op in self.operations(ctx.batch_id)):
            raise ConflictError("já há uma correção em lote em andamento neste lote")
        report = self._report(ctx)
        if scope_kind == "document":
            if not any(d["id"] == scope_id for d in report["documents"]):
                raise NotFoundError("documento não encontrado neste lote")
        else:
            scope_id = ctx.batch_id
        assert scope_id is not None
        plan = plan_bulk(report, scope_kind, scope_id)
        operation = {
            "id": str(uuid.uuid4()),
            "batch_id": ctx.batch_id,
            "scope": {"kind": scope_kind, "id": scope_id},
            "status": "queued",
            "progress": {"done": 0, "total": plan.total, "current": None},
            "reviewer": reviewer,
            "started_at": iso(self.clock.now()),
        }
        self.store.create_operation(operation)
        return operation

    def run_bulk(self, ctx: BatchContext, operation_id: str) -> None:
        """Executa a operação: decide ``correct`` no que é automático, página a página.

        O progresso é gravado a cada unidade (página ou documento). Falha numa
        página não interrompe as outras: ela volta em ``skipped`` como ``failed``.
        """
        op = self.store.get_operation(operation_id)
        if op is None:
            raise NotFoundError("operação não encontrada")
        reviewer = op["reviewer"]
        try:
            report = self._report(ctx)
            plan = plan_bulk(report, op["scope"]["kind"], op["scope"]["id"])
            self.store.update_operation(operation_id, status="running", total=plan.total, done=0)
            pages = {p["id"]: p for p in report["pages"]}
            current = {f["id"]: f for f in report["findings"]}
            applied_by_rule: Counter[str] = Counter()
            skipped = list(plan.skipped)
            pages_result: list[dict[str, Any]] = []
            for done, unit in enumerate(plan.units, start=1):
                self.store.update_operation(operation_id, current=unit.label)
                now = self.clock.now()
                try:
                    if unit.image_findings and unit.page_id is not None:
                        decided_images = [
                            decide(f, DecisionAction.CORRECT, reviewer, now, None, operation_id)
                            for f in unit.image_findings
                        ]
                        state = dict(current)
                        state.update({f["id"]: f for f in decided_images})
                        chain = active_chain(
                            [finding_from_json(f) for f in state.values()], unit.page_id
                        )
                        info = self._refresh(
                            ctx,
                            pages[unit.page_id],
                            chain,
                            event="applied",
                            finding_ids=[f["id"] for f in unit.image_findings],
                            reviewer=reviewer,
                            now=now,
                            operation_id=operation_id,
                        )
                        pages_result.append(
                            {
                                "page_id": unit.page_id,
                                "actions": [f["correction"]["action"] for f in unit.image_findings],
                                "remaining_rules": info["remaining_rules"],
                            }
                        )
                    decided = [
                        decide(f, DecisionAction.CORRECT, reviewer, now, None, operation_id)
                        for f in unit.findings
                    ]
                    self.store.record_decisions(ctx.batch_id, decided, None)
                    for finding in decided:
                        current[finding["id"]] = finding
                        applied_by_rule[finding["rule"]] += 1
                except (LoadError, OSError, CorrectionNotApplicableError) as exc:
                    skipped.extend(
                        skip_entry(f, SkipCategory.FAILED, f"Não foi possível corrigir: {exc}")
                        for f in unit.findings
                    )
                self.store.update_operation(operation_id, done=done)
            final = self._report(ctx)
            self.store.set_summary(ctx.batch_id, recompute_summary(final, ctx.profile))
            self.store.update_operation(
                operation_id,
                status="applied",
                current=None,
                finished_at=iso(self.clock.now()),
                result={
                    "applied_total": sum(applied_by_rule.values()),
                    "applied_by_rule": dict(sorted(applied_by_rule.items())),
                    "skipped_total": len(skipped),
                    "skipped": skipped,
                    "pages": pages_result,
                },
            )
        except Exception as exc:
            self.store.update_operation(
                operation_id,
                status="failed",
                current=None,
                finished_at=iso(self.clock.now()),
                error=f"{exc.__class__.__name__}: {exc}"[:500],
            )
            raise

    def undo_bulk(self, ctx: BatchContext, operation_id: str, reviewer: str) -> dict[str, Any]:
        """Desfaz só as decisões que ainda carregam o identificador desta operação.

        Raises:
            NotFoundError: operação inexistente ou de outro lote.
            ConflictError: operação em andamento ou já desfeita.
        """
        op = self.store.get_operation(operation_id)
        if op is None or op["batch_id"] != ctx.batch_id:
            raise NotFoundError("operação não encontrada")
        if op["status"] not in UNDOABLE:
            raise ConflictError(f"operação {op['status']}: não há o que desfazer")
        report = self._report(ctx)
        now = self.clock.now()
        targets = [
            f
            for f in report["findings"]
            if (f.get("decision") or {}).get("operation_id") == operation_id
        ]
        cleared = [{k: v for k, v in f.items() if k != "decision"} for f in targets]
        by_id = {f["id"]: f for f in cleared}
        report["findings"] = [by_id.get(f["id"], f) for f in report["findings"]]
        parsed = [finding_from_json(f) for f in report["findings"]]
        pages = {p["id"]: p for p in report["pages"]}
        touched = sorted(
            {
                f["target"]["id"]
                for f in cleared
                if f["target"]["kind"] == "page"
                and CorrectionAction(f["correction"]["action"]) in IMAGE_ACTIONS
            }
        )
        for page_id in touched:
            self._refresh(
                ctx,
                pages[page_id],
                active_chain(parsed, page_id),
                event="undone",
                finding_ids=[f["id"] for f in cleared if f["target"]["id"] == page_id],
                reviewer=reviewer,
                now=now,
                operation_id=operation_id,
            )
        summary = recompute_summary(report, ctx.profile)
        self.store.clear_decisions(ctx.batch_id, cleared, reviewer, iso(now), operation_id, summary)
        undo = {
            "undone_total": len(cleared),
            "undone_by_rule": dict(sorted(Counter(f["rule"] for f in cleared).items())),
            "reviewer": reviewer,
            "at": iso(now),
        }
        self.store.update_operation(operation_id, status="undone", undo=undo)
        return self.operation(operation_id)

    # Lote corrigido -------------------------------------------------------------------

    def plan(self, ctx: BatchContext) -> dict[str, Any]:
        """Plano do lote corrigido com as decisões atuais."""
        return build_plan(self._report(ctx), self.operations(ctx.batch_id))

    def corrected_image(self, ctx: BatchContext, page_id: str) -> NDArray[np.uint8] | None:
        """Versão corrigida mais recente da página (``None`` se não há correção).

        Raises:
            NotFoundError: página fora do lote.
        """
        report = self._report(ctx)
        page = next((p for p in report["pages"] if p["id"] == page_id), None)
        if page is None:
            raise NotFoundError("página não encontrada")
        return self._final_image(ctx, page, [finding_from_json(f) for f in report["findings"]])

    def save(
        self,
        ctx: BatchContext,
        reviewer: str,
        writer_factory: Callable[[datetime], CorrectedBatchWriter],
        *,
        destination: str = "zip",
        check_source: Callable[[], Sequence[str]] | None = None,
    ) -> dict[str, Any]:
        """Salva as correções: confirma as operações e gera o lote corrigido.

        O zip tem a mesma estrutura de pastas, a ordem final, as páginas
        removidas fora, a versão corrigida mais recente de cada página, arquivos
        renumerados, TIFF sem perda com o DPI do original e o manifesto.

        Args:
            ctx: contexto do lote.
            reviewer: quem salvou.
            writer_factory: cria o gravador (``.zip`` ou pasta) para o horário da gravação.
            destination: ``zip`` ou ``folder``, devolvido na resposta.
            check_source: devolve o que mudou na pasta original desde a análise.

        Raises:
            SaveBlockedError: há página faltando sem decisão.
            SourceChangedError: a pasta original mudou desde a análise.
            ConflictError: há correção em lote em andamento.
        """
        operations = self.operations(ctx.batch_id)
        if any(op["status"] in {"queued", "running"} for op in operations):
            raise ConflictError("espere a correção em lote terminar antes de salvar")
        report = self._report(ctx)
        plan = build_plan(report, operations)
        if not plan["can_save"]:
            raise SaveBlockedError(plan["blockers"])
        changes = list(check_source()) if check_source is not None else []
        if changes:
            raise SourceChangedError(changes)
        now = self.clock.now()
        pages = {p["id"]: p for p in report["pages"]}
        parsed = [finding_from_json(f) for f in report["findings"]]
        tags_cache: dict[str, dict[str, str]] = {}
        writer = writer_factory(now)
        try:
            for doc in plan["documents"]:
                exported = sorted(
                    (p for p in doc["pages"] if p["status"] == "exported"),
                    key=lambda p: p["new_position"],
                )
                for item in exported:
                    page = pages[item["page_id"]]
                    image = self._final_image(ctx, page, parsed)
                    if image is None:
                        image = self._loader(ctx, page)()
                    item["target_sha256"] = writer.add_page(
                        item["target_file"],
                        image,
                        item["dpi"],
                        page.get("color_mode") == "bilevel",
                        self._tags(ctx, page["source_file"], tags_cache),
                    )
            manifest = {
                "batch_id": ctx.batch_id,
                "batch_name": ctx.name,
                "generated_at": iso(now),
                "generated_by": reviewer,
                "engine_version": self.engine_version,
                "format": "TIFF",
                "compression": "tiff_deflate",
                "original_unchanged": True,
                "totals": plan_totals(plan["documents"]),
                "documents": plan["documents"],
            }
            validate(manifest, "corrected-manifest.schema.json")
            writer.add_text(
                "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
            )
            writer.add_text("manifest.csv", manifest_csv(manifest))
            writer.add_text("report.json", json.dumps(report, ensure_ascii=False, indent=2) + "\n")
            page_index = {p["id"]: p for p in report["pages"]}
            writer.add_text("findings.csv", findings_csv(report["findings"], page_index))
            writer.add_text("decisions.csv", decisions_csv(self.store.decision_log(ctx.batch_id)))
            path, sha, size = writer.close()
        except BaseException:
            writer.abort()
            raise
        for op_id in plan["unsaved_operations"]:
            self.store.update_operation(op_id, status="saved", saved_at=iso(now))
        zipped = destination == "zip"
        return {
            "file": path.name,
            "download": f"/batches/{ctx.batch_id}/exports/{path.name}" if zipped else None,
            "destination": destination,
            "folder": None if zipped else display_path(str(path)),
            "size_bytes": size,
            "sha256": sha,
            "generated_at": iso(now),
            "totals": manifest["totals"],
            "pending_critical": plan["pending_critical"],
            "saved_operations": list(plan["unsaved_operations"]),
        }

    def _tags(
        self, ctx: BatchContext, source: str, cache: dict[str, dict[str, str]]
    ) -> dict[str, str]:
        """Tags de captura do original (equipamento, data, operador) para o TIFF corrigido."""
        if source not in cache:
            try:
                tags = dict(self.metadata.read(ctx.root / source).tags)
            except OSError:
                tags = {}
            kept = {k: str(tags[k]) for k in ("make", "model", "datetime", "artist") if tags.get(k)}
            kept["software"] = f"qa-digitalizacao {self.engine_version} (lote corrigido)"
            cache[source] = kept
        return cache[source]
