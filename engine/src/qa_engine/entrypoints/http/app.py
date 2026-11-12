"""Aplicação FastAPI. Rotas e formatos seguem ``contracts/openapi.yaml``.

Corpos de requisição e de resposta são validados contra os JSON Schemas do
contrato (``application.contracts``), em vez de modelos escritos à mão.
"""

from __future__ import annotations

import asyncio
import getpass
import hashlib
import io
import json
import logging
import platform
import secrets
import shutil
import threading
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import cv2
import yaml
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from qa_engine import __version__
from qa_engine.adapters.box_report_pdf import render_box_report_pdf
from qa_engine.adapters.corrected_folder import FolderTiffWriter
from qa_engine.adapters.corrected_zip import ZipTiffWriter
from qa_engine.adapters.feedback import SqliteFeedbackStore
from qa_engine.adapters.images import FileImageSource
from qa_engine.adapters.local_folder import LocalFolderSource, is_within
from qa_engine.adapters.metadata import PillowMetadataReader
from qa_engine.adapters.page_versions import FilePageVersionStore
from qa_engine.adapters.shared_diagnostics import SharedDiagnosticsFolder
from qa_engine.adapters.shared_reports import SharedReportsFolder
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.adapters.system import SystemClock, total_memory_mb
from qa_engine.application.admin import AttemptLimiter, verify_token
from qa_engine.application.analyze import BatchAnalysis, PageTask, analyze_page, evaluate_page
from qa_engine.application.beta import metrics_for
from qa_engine.application.box_report import (
    boxes,
    build_box_report,
    is_complete,
    pendencies_key,
)
from qa_engine.application.complements import (
    COMPLEMENTS_DIR,
    complement_source,
    insert_page,
    is_complement,
    marks_for_report,
    page_path,
    remove_page,
    suggest_position,
)
from qa_engine.application.contracts import ContractError, validate
from qa_engine.application.correction_service import (
    CORRECTED_ZIP,
    BatchContext,
    ConflictError,
    CorrectionService,
    NotFoundError,
    SaveBlockedError,
    SourceChangedError,
)
from qa_engine.application.demo_batches import copy_demo_batch, list_demo_batches
from qa_engine.application.diagnostics import (
    export_package,
    filtered,
    groups,
    record_from_client,
    record_from_crash_file,
    record_from_exception,
)
from qa_engine.application.diagnostics import summary as diagnostics_summary
from qa_engine.application.exports import findings_csv, metadata_csv, rework_csv
from qa_engine.application.feedback import numbering_example, orientation_example
from qa_engine.application.local_batch import (
    SNAPSHOT_FILE,
    LocalBatchError,
    compare_snapshot,
    open_local_batch,
    take_snapshot,
    wait_until_stable,
)
from qa_engine.application.management import management_view
from qa_engine.application.models import verify_models
from qa_engine.application.profile import Profile, load_profile, profile_from_dict
from qa_engine.application.release import merge_release, queue_of
from qa_engine.application.review import (
    SEQUENCE_RULES,
    ManualOrder,
    baselines_from_json,
    baselines_json,
    finding_from_json,
    set_manual_numbering,
)
from qa_engine.application.serialize import analysis_json, finding_json, iso
from qa_engine.application.services import run_analysis
from qa_engine.application.settings import ResolvedSettings, SettingsError, SettingsProblem
from qa_engine.detectors import duplicate_page
from qa_engine.detectors.registry import PAGE_DETECTORS
from qa_engine.domain import ids
from qa_engine.domain.model import DecisionAction
from qa_engine.domain.sequencing import parse_folio
from qa_engine.entrypoints.http.settings import Settings, normalize_origin, server_settings
from qa_engine.entrypoints.http.uploads import (
    UploadError,
    extract_zip,
    safe_relative,
    strip_common_root,
)
from qa_engine.ports import LoadError, SettingsSource

log = logging.getLogger("qa_engine.http")
API_PREFIXES = (
    "/batches",
    "/findings",
    "/bulk-corrections",
    "/pages",
    "/documents",
    "/profiles",
    "/demo-batches",
    "/local-batches",
    "/session",
    "/settings",
    "/diagnostics",
    "/admin",
)
"""Rotas que exigem token quando ``QA_API_TOKEN`` está definido. O resto (saúde,
documentação e a interface servida na mesma origem) é público."""
PUBLIC = {"/session/exchange"}
"""Rotas dentro dos prefixos protegidos que não exigem token (elas próprias conferem)."""
CODE_TTL_SECONDS = 120.0
"""Validade do código de uso único entregue no fragmento da URL."""
PROFILE_SNAPSHOT = "profile.json"
"""Cópia do perfil efetivo, gravada na pasta de trabalho de cada lote analisado."""
EXPORTS = {
    "report.json": "application/json",
    "findings.csv": "text/csv; charset=utf-8",
    "metadata.csv": "text/csv; charset=utf-8",
    "rework_order.csv": "text/csv; charset=utf-8",
    CORRECTED_ZIP: "application/zip",
}


def problem(status: int, title: str, detail: str | None = None) -> JSONResponse:
    """Resposta de erro no formato RFC 9457."""
    body: dict[str, Any] = {"title": title, "status": status}
    if detail:
        body["detail"] = detail
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


class Engine:
    """Estado do serviço: repositório, perfis e fila de análise."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.repo = SqliteRepository(settings.data_dir / "qa.sqlite3")
        self.queue = ThreadPoolExecutor(max_workers=1, thread_name_prefix="analysis")
        self.corrections = ThreadPoolExecutor(max_workers=1, thread_name_prefix="corrections")
        self.images = FileImageSource()
        self.folder = LocalFolderSource()
        self.feedback = SqliteFeedbackStore(self.repo, settings.data_dir)
        self.shared = (
            SharedDiagnosticsFolder(settings.diagnostics_dir) if settings.diagnostics_dir else None
        )
        self.admin_attempts = AttemptLimiter()
        self.models = verify_models(settings.models_dir)
        if not self.models.ok:
            log.error("modelos com problema: %s", "; ".join(self.models.problems))
        self.last_request = time.monotonic()
        self._codes: dict[str, float] = {}
        self._codes_lock = threading.Lock()
        self.service = CorrectionService(
            self.repo, self.images, PillowMetadataReader(), SystemClock(), __version__
        )

    def now(self) -> datetime:
        """Agora, em UTC."""
        return datetime.now(tz=UTC)

    def batch_dir(self, batch_id: str) -> Path:
        """Pasta de trabalho de um lote."""
        return self.settings.data_dir / "batches" / batch_id

    def profile(self, profile_id: str) -> Profile:
        """Perfil pelo identificador."""
        path = self.settings.profiles_dir / f"{profile_id}.yaml"
        if not path.is_file():
            raise HTTPException(404, f"perfil {profile_id!r} não encontrado")
        return load_profile(path)

    def batch_profile(self, batch_id: str, profile_id: str) -> Profile:
        """Perfil com que o lote foi analisado: a cópia gravada com ele, se houver.

        Assim o resultado continua explicável mesmo que o perfil mude depois.
        """
        snapshot = self.batch_dir(batch_id) / PROFILE_SNAPSHOT
        if snapshot.is_file():
            return profile_from_dict(json.loads(snapshot.read_text("utf-8")))
        return self.profile(profile_id)

    def record(self, record: dict[str, Any]) -> None:
        """Grava um registro de diagnóstico no banco e, se houver, na pasta compartilhada."""
        try:
            self.repo.add_diagnostic(record)
        except Exception:
            log.exception("falha ao gravar diagnóstico")
        if self.shared is not None:
            self.shared.append(record)

    def record_error(
        self,
        error: BaseException,
        origin: str,
        where: str | None,
        batch_id: str | None = None,
        severity: str = "error",
    ) -> None:
        """Registra uma exceção do motor ou de um processo de análise."""
        self.record(
            record_from_exception(
                error,
                origin=origin,
                severity=severity,
                where=where,
                version=__version__,
                user=os_user() if self.settings.mode == "desktop" else None,
                batch_id=batch_id,
            )
        )

    def ingest_crashes(self) -> None:
        """Lê os arquivos de queda da abertura e os registra uma vez (o id vem do nome)."""
        folder = self.settings.data_dir / "logs"
        for path in sorted(folder.glob("crash-*.txt")) if folder.is_dir() else []:
            try:
                self.record(record_from_crash_file(path.read_text("utf-8"), path.name, __version__))
                path.rename(path.with_suffix(".registrado.txt"))
            except OSError:
                log.warning("arquivo de queda ilegível: %s", path.name)

    def all_diagnostics(self) -> list[dict[str, Any]]:
        """Registros deste computador e, se houver, os da pasta compartilhada (sem repetir)."""
        records = {r["id"]: r for r in self.repo.diagnostics()}
        if self.shared is not None:
            records.update({r["id"]: r for r in self.shared.read_all() if "id" in r})
        return sorted(records.values(), key=lambda r: r["at"])

    def issue_code(self) -> str:
        """Código de uso único para abrir a interface no navegador padrão (desktop)."""
        code = secrets.token_urlsafe(24)
        with self._codes_lock:
            self._codes[code] = time.monotonic() + CODE_TTL_SECONDS
        return code

    def redeem_code(self, code: str) -> bool:
        """Consome o código; verdadeiro se ele existia e não tinha vencido."""
        with self._codes_lock:
            expires = self._codes.pop(code, None)
            now = time.monotonic()
            self._codes = {c: t for c, t in self._codes.items() if t > now}
        return expires is not None and expires > now

    def source_changes(self, batch_id: str, root: Path) -> list[str]:
        """O que mudou na pasta original desde o retrato (lote local; senão, nada)."""
        snapshot = self.batch_dir(batch_id) / SNAPSHOT_FILE
        if not snapshot.is_file():
            return []
        return compare_snapshot(self.folder, root, json.loads(snapshot.read_text("utf-8")))

    def release(self, batch_id: str, root: Path, profile: Profile, analysis: BatchAnalysis) -> None:
        """Grava um relatório parcial (processo pronto) ou o final, mesclando com o gravado.

        O conferente pode estar decidindo ou digitando numeração enquanto o resto da caixa
        é analisado: ler, mesclar e gravar acontecem com o banco seguro.
        """
        if analysis.numbering_crops:
            crops = self.batch_dir(batch_id) / NUMBERING_CROPS
            crops.mkdir(parents=True, exist_ok=True)
            for page_id, png in analysis.numbering_crops.items():
                target = crops / f"{page_id}.png"
                if not target.exists():
                    target.write_bytes(png)
        fresh = analysis_json(analysis)
        with self.repo.locked():
            report = merge_release(
                self.repo.get_report(batch_id),
                fresh,
                profile,
                root,
                final=analysis.final,
                overrides=self.repo.numbering_overrides(batch_id),
                manual_orders=_orders(self.repo.manual_orders(batch_id)),
            )
            validate(report, "analysis.schema.json")
            queue = None if analysis.final else queue_of(report, analysis.pending_documents)
            self.repo.save_report(batch_id, report, final=analysis.final, queue=queue)

    def beta_metrics(self, batch_id: str) -> dict[str, Any] | None:
        """Contagens do lote para o relatório do beta, conferindo o original quando dá."""
        row = self.repo.get_batch(batch_id)

        def changes() -> list[str] | None:
            if row is None or row.source != "local" or not row.root.is_dir():
                return None
            try:
                return self.source_changes(batch_id, row.root)
            except OSError:
                return None

        return metrics_for(self.repo, batch_id, changes)

    def generate_box_reports(self, batch_id: str, reviewer: str) -> list[dict[str, Any]]:
        """Relatório de cada caixa concluída; versão nova só quando as pendências mudaram.

        Só depois da passada final: antes dela um achado novo ainda pode aparecer.
        """
        row = self.repo.get_batch(batch_id)
        report = self.repo.get_report(batch_id)
        if row is None or report is None or row.status != "analyzed":
            raise HTTPException(409, "a caixa ainda está em análise")
        history: dict[str, list[dict[str, Any]]] = {}
        for item in self.repo.box_reports(batch_id):
            history.setdefault(item["report"]["box"], []).append(item)
        made: list[dict[str, Any]] = []
        for box, docs in boxes(report).items():
            if not is_complete(report, docs):
                continue
            previous = history.get(box, [])
            last = previous[-1] if previous else None
            built = build_box_report(
                report,
                box,
                docs,
                reviewer=reviewer,
                concluded_at=iso(self.now()),
                machine=platform.node() or "estação",
                program_version=__version__,
                version=(last["report"]["version"] + 1) if last else 1,
                previous_pending=bool(last and last["report"]["state"] == "pending"),
            )
            key = pendencies_key(built)
            if last is not None and last["pendencies"] == key:
                continue
            validate(built, "box-report.schema.json")
            report_id = str(uuid.uuid4())
            self.repo.add_box_report(report_id, built, key)
            self.write_box_report(built)
            made.append({"id": report_id, "report": built})
        return made

    def write_box_report(self, built: Mapping[str, Any]) -> None:
        """Grava JSON e PDF na pasta de saída e, com ``reports_dir``, na pasta compartilhada."""
        if self.settings.mode == "cloud":
            return
        pdf = render_box_report_pdf(built)
        text = json.dumps(built, ensure_ascii=False, indent=2)
        box = safe_name(built["box"])
        local = self.settings.output_root / "Relatórios por caixa" / safe_name(built["batch_name"])
        targets = [(local, f"{box}-v{built['version']}")]
        if self.settings.reports_dir is not None:
            machine = safe_name(built["machine"])
            shared = self.settings.reports_dir / machine
            targets.append((shared, f"{box}-{built['batch_id'][:8]}-v{built['version']}"))
        for folder, stem in targets:
            try:
                folder.mkdir(parents=True, exist_ok=True)
                for suffix, data in ((".json", text.encode("utf-8")), (".pdf", pdf)):
                    part = folder / f"{stem}{suffix}.part"
                    part.write_bytes(data)
                    part.replace(folder / f"{stem}{suffix}")
            except OSError as exc:
                log.warning("não foi possível gravar o relatório da caixa em %s", folder)
                self.record_error(exc, "engine", "relatório por caixa", None, "warning")

    def insert_complement(
        self,
        batch_id: str,
        document_id: str,
        filename: str,
        data: bytes,
        position: int | None,
        reviewer: str,
    ) -> dict[str, Any]:
        """Folha que apareceu depois: guarda, analisa, encaixa e resolve a sequência de novo.

        A folha fica na área de complementos da pasta de trabalho, nunca na pasta original.
        """
        row = self.repo.get_batch(batch_id)
        if row is None:
            raise HTTPException(404, "lote não encontrado")
        if row.status != "analyzed":
            raise HTTPException(409, "espere a análise da caixa terminar")
        suffix = Path(filename).suffix.lower()
        if suffix not in {".tif", ".tiff", ".png", ".jpg", ".jpeg", ".pdf"}:
            raise HTTPException(422, "a folha precisa ser TIFF, PNG, JPEG ou PDF")
        ctx = self.context(batch_id)
        profile = ctx.profile
        folder = self.batch_dir(batch_id) / COMPLEMENTS_DIR
        folder.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4().hex}{suffix}"
        path = folder / name
        path.write_bytes(data)
        try:
            count = self.images.page_count(path)
        except LoadError as exc:
            path.unlink(missing_ok=True)
            raise HTTPException(422, f"não foi possível ler a folha: {exc}") from exc
        if count != 1:
            path.unlink(missing_ok=True)
            raise HTTPException(422, "solte uma folha por vez (o arquivo tem mais de uma página)")
        station = profile.station(self.settings.default_station)
        station_id = station.id if station is not None else None
        rules = tuple(
            (d.id, profile.params(d.id, station_id))
            for d in PAGE_DETECTORS
            if profile.enabled(d.id, station_id)
        )
        models = self.settings.models_dir if self.models.checked else None
        reader = profile.numbering_reader if profile.numbering_enabled and models else None
        task = PageTask(
            path,
            0,
            rules,
            float(profile.params(duplicate_page.ID, station_id)["min_ink_coverage"]),
            models,
            reader,
            reader,
        )
        result = analyze_page(task, self.images)
        source_file = complement_source(name)
        page_id = ids.page_id(batch_id, source_file, 0)
        sha = hashlib.sha256(data).hexdigest()
        page = {
            "id": page_id,
            "document_id": document_id,
            "index": 0,
            "source_file": source_file,
            "page_in_file": 0,
            "width_px": result.width_px,
            "height_px": result.height_px,
            "dpi": result.dpi,
            "color_mode": result.color_mode.value if result.color_mode else None,
            "sha256": sha,
            "loaded": result.error is None,
            "station": station.location if station is not None else "não identificada",
            "station_id": station_id,
        }
        found = [
            finding_json(f)
            for f in evaluate_page(
                batch_id,
                page_id,
                result,
                profile,
                ctx.baselines,
                station_id,
                has_numbering=bool(result.marks),
            )
        ]
        live = [m for m in result.marks if not m.struck]
        folio = parse_folio(live[0].readings[0].text) if live and live[0].readings else None
        if result.numbering_crop:
            crops = self.batch_dir(batch_id) / NUMBERING_CROPS
            crops.mkdir(parents=True, exist_ok=True)
            (crops / f"{page_id}.png").write_bytes(result.numbering_crop)
        now = iso(self.now())
        with self.repo.locked():
            report = self.repo.get_report(batch_id)
            if report is None or not any(d["id"] == document_id for d in report["documents"]):
                path.unlink(missing_ok=True)
                raise HTTPException(404, "processo não encontrado neste lote")
            suggested = suggest_position(report, document_id, folio)
            chosen = suggested if position is None else max(0, position - 1)
            new = insert_page(
                report,
                profile,
                row.root,
                document_id,
                page,
                found,
                marks_for_report(result.marks),
                chosen,
                self.repo.numbering_overrides(batch_id),
                _orders(self.repo.manual_orders(batch_id)),
            )
            validate(new, "analysis.schema.json")
            self.repo.add_complement(
                {
                    "batch_id": batch_id,
                    "file": name,
                    "position": chosen + 1,
                    "reviewer": reviewer,
                    "at": now,
                },
                page,
            )
            self.repo.replace_report(batch_id, new)
        self.generate_box_reports(batch_id, reviewer)
        return self.document_view(new, document_id) | {
            "page_id": page_id,
            "position": chosen + 1,
            "suggested_position": suggested + 1,
            "folio_read": str(folio) if folio is not None else None,
        }

    def remove_complement(self, batch_id: str, page_id: str, reviewer: str) -> dict[str, Any]:
        """Desfaz a inserção de uma folha (a auditoria fica)."""
        row = self.repo.get_batch(batch_id)
        if row is None:
            raise HTTPException(404, "lote não encontrado")
        profile = self.batch_profile(batch_id, row.profile_id)
        with self.repo.locked():
            report = self.repo.get_report(batch_id)
            page = next((p for p in (report or {}).get("pages", []) if p["id"] == page_id), None)
            if report is None or page is None:
                raise HTTPException(404, "página não encontrada")
            if not is_complement(page["source_file"]):
                raise HTTPException(409, "só uma folha inserida depois pode ser removida")
            document_id = page["document_id"]
            new = remove_page(
                report,
                profile,
                row.root,
                page_id,
                self.repo.numbering_overrides(batch_id),
                _orders(self.repo.manual_orders(batch_id)),
            )
            orders = self.repo.manual_orders(batch_id)
            if document_id in orders:
                kept = [p for p in orders[document_id]["page_ids"] if p != page_id]
                self.repo.set_manual_order(document_id, batch_id, kept, reviewer, iso(self.now()))
            self.repo.remove_complement(page_id, reviewer, iso(self.now()))
            self.repo.replace_report(batch_id, new)
        page_path(row.root, self.batch_dir(batch_id), page["source_file"]).unlink(missing_ok=True)
        self.generate_box_reports(batch_id, reviewer)
        return self.document_view(new, document_id)

    @staticmethod
    def document_view(report: Mapping[str, Any], document_id: str) -> dict[str, Any]:
        """Documento depois de uma mudança (``document-numbering.schema.json``)."""
        doc = next(d for d in report["documents"] if d["id"] == document_id)
        ids_ = set(doc["page_ids"]) | {document_id}
        return {
            "document": doc,
            "pages": {
                p["id"]: p["numbering"]
                for p in report["pages"]
                if p["id"] in ids_ and "numbering" in p
            },
            "findings": [f for f in report["findings"] if f["target"]["id"] in ids_],
            "summary": report["batch"]["summary"],
        }

    def collect_numbering(
        self,
        batch_id: str,
        profile: Profile,
        before: Mapping[str, Any],
        values: Mapping[str, str | None],
        reviewer: str,
        at: str,
    ) -> None:
        """Coleta do beta: numeração digitada vira exemplo (desfazer apaga o exemplo)."""
        if not profile.feedback_enabled:
            return
        pages = {p["id"]: p for p in before["pages"]}
        for page_id, value in values.items():
            if value is None:
                self.feedback.remove("numbering", page_id)
                continue
            crop = self.batch_dir(batch_id) / NUMBERING_CROPS / f"{page_id}.png"
            self.feedback.add(
                numbering_example(
                    batch_id,
                    pages[page_id],
                    value,
                    reviewer,
                    at,
                    profile.feedback_retention_days,
                    crop.read_bytes() if crop.is_file() else None,
                )
            )

    def collect_orientation(self, batch_id: str, profile: Profile, finding_id: str) -> None:
        """Coleta do beta: decisão de orientação do revisor vira exemplo."""
        if not profile.feedback_enabled:
            return
        found = self.repo.get_finding(finding_id)
        if found is None or found[1]["rule"] != "orientation":
            return
        finding = found[1]
        page_id = finding["target"]["id"]
        decision = finding.get("decision")
        if not decision:
            self.feedback.remove("orientation", page_id)
            return
        thumb = None
        page = self.repo.get_page(page_id)
        row = self.repo.get_batch(batch_id)
        if page is not None and row is not None:
            try:
                img = self.images.load_original(
                    page_path(row.root, self.batch_dir(batch_id), page["source_file"]),
                    page["page_in_file"],
                )
                h = max(1, round(img.shape[0] * THUMB_WIDTH / img.shape[1]))
                buf = io.BytesIO()
                small = cv2.resize(img, (THUMB_WIDTH, h), interpolation=cv2.INTER_AREA)
                Image.fromarray(small).save(buf, format="PNG")
                thumb = buf.getvalue()
            except (OSError, ValueError, LoadError):
                thumb = None
        example = orientation_example(
            batch_id,
            finding,
            decision.get("reviewer", "revisor"),
            decision.get("decided_at") or iso(self.now()),
            profile.feedback_retention_days,
            thumb,
        )
        if example is not None:
            self.feedback.add(example)

    def context(self, batch_id: str) -> BatchContext:
        """Contexto dos casos de uso de correção para um lote."""
        row = self.repo.get_batch(batch_id)
        if row is None:
            raise HTTPException(404, "lote não encontrado")
        work = self.batch_dir(batch_id)
        baselines_path = work / "baselines.json"
        baselines = (
            baselines_from_json(json.loads(baselines_path.read_text("utf-8")))
            if baselines_path.is_file()
            else {}
        )
        return BatchContext(
            batch_id=batch_id,
            name=row.name,
            root=row.root,
            profile=self.batch_profile(batch_id, row.profile_id),
            baselines=baselines,
            versions=FilePageVersionStore(work / "corrected"),
            work=work,
        )

    def run_bulk(self, batch_id: str, operation_id: str) -> None:
        """Trabalho de fundo do "Corrigir tudo"."""
        try:
            self.service.run_bulk(self.context(batch_id), operation_id)
        except Exception as exc:
            log.exception("falha na correção em lote %s", operation_id)
            self.record_error(exc, "worker", "correção em lote", batch_id)

    def purge(self) -> None:
        """Apaga lotes mais antigos que a retenção.

        Só a pasta de trabalho do lote (dentro de ``data_dir``) é apagada. A pasta de um
        lote local é o original e nunca é tocada.
        """
        cutoff = iso(self.now() - timedelta(hours=self.settings.retention_hours))
        # As contagens do beta ficam: só números, nada de conteúdo de documento.
        for batch_id in self.repo.batches_before(cutoff):
            metrics = self.beta_metrics(batch_id)
            if metrics is not None:
                self.repo.save_beta_metrics(batch_id, metrics["created_at"], metrics)
        self.feedback.purge(iso(self.now()))
        for batch_id in self.repo.purge_before(cutoff):
            shutil.rmtree(self.batch_dir(batch_id), ignore_errors=True)

    def analyze(
        self,
        batch_id: str,
        root: Path,
        profile: Profile,
        name: str,
        station_id: str | None = None,
        local: bool = False,
    ) -> None:
        """Trabalho de fundo: analisa e grava o resultado.

        Lote local: antes, espera a pasta parar de mudar e tira o retrato dos arquivos.
        """
        try:
            work = self.batch_dir(batch_id)
            work.mkdir(parents=True, exist_ok=True)
            if local:
                self.repo.set_stage(batch_id, "settling")
                wait_until_stable(self.folder, root, self.settings.batch_settle_seconds)
                self.repo.set_stage(batch_id, "snapshot")
                (work / SNAPSHOT_FILE).write_text(
                    json.dumps(take_snapshot(self.folder, root), ensure_ascii=False),
                    encoding="utf-8",
                )
            self.repo.set_stage(batch_id, "analyzing")
            (work / PROFILE_SNAPSHOT).write_text(
                json.dumps(dict(profile.raw), ensure_ascii=False, indent=2), encoding="utf-8"
            )
            analysis = run_analysis(
                root,
                profile,
                workers=self.settings.effective_workers(memory_mb=total_memory_mb()),
                name=name,
                batch_id=batch_id,
                progress=lambda done, total: self.repo.set_progress(batch_id, done, total),
                fallback_station=station_id or self.settings.default_station,
                models_dir=self.settings.models_dir if self.models.checked else None,
                on_document=lambda partial, _doc: self.release(batch_id, root, profile, partial),
            )
            (self.batch_dir(batch_id) / "baselines.json").write_text(
                json.dumps(baselines_json(analysis.baselines)), encoding="utf-8"
            )
            self.release(batch_id, root, profile, analysis)
        except Exception as exc:
            log.exception("falha na análise do lote %s", batch_id)
            self.record_error(exc, "worker", "análise do lote", batch_id, "critical")
            self.repo.fail(batch_id, f"{exc.__class__.__name__}: {exc}"[:500])


THUMB_WIDTH = 256
"""Largura da miniatura guardada nos exemplos de orientação da coleta do beta."""
NUMBERING_CROPS = "numbering"
"""Pasta, dentro da pasta de trabalho do lote, com o recorte da numeração de cada página."""


def _orders(rows: Mapping[str, Mapping[str, Any]]) -> dict[str, ManualOrder]:
    return {
        doc: ManualOrder(tuple(o["page_ids"]), o["reviewer"], o["decided_at"])
        for doc, o in rows.items()
    }


def safe_name(text: str) -> str:
    """Nome de arquivo seguro no Windows: sem barras, caracteres reservados nem espaço no fim."""
    cleaned = "".join("_" if ch in '\\/:*?"<>|' or ord(ch) < 32 else ch for ch in str(text))
    return cleaned.strip(" .") or "sem-nome"


def capabilities(settings: Settings, demo_batches: int, editable: bool = False) -> list[str]:
    """O que o motor oferece, conforme o modo (``capabilities`` em ``/health``).

    Args:
        settings: configuração efetiva.
        demo_batches: lotes de demonstração prontos.
        editable: há camada de configuração editável pela tela.
    """
    if settings.mode == "desktop":
        caps = ["local_batches", "folder_export", "os_session"]
        return [*caps, "settings"] if editable else caps
    caps = ["upload", "folder_export"] if settings.mode == "server" else ["upload"]
    if demo_batches:
        caps.append("demo_batches")
    if settings.mode == "cloud":
        caps.append("synthetic_only")
    return caps


def os_user() -> str:
    """Usuário do sistema operacional, gravado como revisor no programa desktop."""
    try:
        return getpass.getuser()
    except (KeyError, OSError):
        return "usuário"


USER_EDITABLE = (
    "workers",
    "max_memory_mb",
    "output_dir",
    "temp_dir",
    "data_dir",
    "allowed_roots",
    "default_station",
    "batch_settle_seconds",
    "retention_days",
    "log_level",
)
"""Chaves de configuração que a pessoa muda pela tela (as travadas pela máquina saem)."""


def settings_view(resolved: ResolvedSettings, restart_required: bool) -> dict[str, Any]:
    """Configuração no formato de ``settings-view.schema.json``."""
    view = resolved.json()
    view["editable"] = [k for k in USER_EDITABLE if k not in resolved.locked]
    view["restart_required"] = restart_required
    return view


def create_app(
    settings: Settings | None = None, settings_source: SettingsSource | None = None
) -> FastAPI:
    """Monta a aplicação.

    Args:
        settings: configuração efetiva (padrão: a do servidor, por variáveis ``QA_*``).
        settings_source: camadas de configuração editáveis pela tela (programa desktop).
    """
    settings = settings or server_settings()
    engine = Engine(settings)
    if settings.api_token is None:
        log.warning("QA_API_TOKEN não definido: API sem autenticação (só desenvolvimento)")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        engine.purge()
        engine.ingest_crashes()
        yield
        engine.queue.shutdown(wait=False, cancel_futures=True)
        engine.corrections.shutdown(wait=False, cancel_futures=True)
        engine.repo.close()

    app = FastAPI(
        title="QA Automático de Digitalização",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.engine = engine

    # Ordem das camadas, de fora para dentro: CORS → erros → autenticação → rotas.
    # Assim toda resposta, inclusive 401 e 500, leva os cabeçalhos CORS; sem eles o
    # navegador esconde o erro real e mostra só "Failed to fetch".
    @app.middleware("http")
    async def auth(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        protected = request.url.path.startswith(API_PREFIXES) and request.url.path not in PUBLIC
        if settings.api_token and protected and request.method != "OPTIONS":
            header = request.headers.get("authorization", "")
            if header != f"Bearer {settings.api_token}":
                return problem(401, "Não autorizado", "Envie Authorization: Bearer <token>.")
        return await call_next(request)

    @app.middleware("http")
    async def trusted_host(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Desktop: outro site aberto na máquina pode tentar chamar 127.0.0.1 com outro Host
        # (DNS rebinding). Só o endereço do próprio programa passa.
        engine.last_request = time.monotonic()
        if settings.trusted_hosts:
            host = request.headers.get("host", "").lower()
            if host not in settings.trusted_hosts:
                return problem(400, "Endereço não aceito", "Abra o programa pelo atalho.")
        return await call_next(request)

    @app.middleware("http")
    async def errors(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception as exc:
            log.exception("erro não tratado em %s %s", request.method, request.url.path)
            route = request.scope.get("route")
            where = f"{request.method} {getattr(route, 'path', request.url.path)}"
            engine.record_error(exc, "engine", where, request.path_params.get("batch_id"))
            return problem(500, "Erro interno do motor", "Veja o log do servidor.")

    origins = sorted({normalize_origin(o) for o in settings.cors_origins})
    if origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
            max_age=600,
        )

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return problem(404, str(exc))

    @app.exception_handler(SettingsError)
    async def settings_error(_: Request, exc: SettingsError) -> JSONResponse:
        body: dict[str, Any] = {
            "title": "Configuração inválida",
            "status": 422,
            "detail": str(exc),
            "problems": [p.json() for p in exc.problems],
        }
        return JSONResponse(body, status_code=422, media_type="application/problem+json")

    @app.exception_handler(LocalBatchError)
    async def local_batch_error(_: Request, exc: LocalBatchError) -> JSONResponse:
        return problem(exc.status, "Pasta não pode ser aberta como lote", str(exc))

    @app.exception_handler(SourceChangedError)
    async def source_changed(_: Request, exc: SourceChangedError) -> JSONResponse:
        return problem(409, "Lote original alterado", str(exc))

    @app.exception_handler(SaveBlockedError)
    async def save_blocked(_: Request, exc: SaveBlockedError) -> JSONResponse:
        return problem(409, "Página faltando sem decisão", str(exc))

    @app.exception_handler(ConflictError)
    async def conflict(_: Request, exc: ConflictError) -> JSONResponse:
        return problem(409, "Conflito", str(exc))

    @app.exception_handler(ContractError)
    async def contract_error(_: Request, exc: ContractError) -> JSONResponse:
        return problem(422, "Documento fora do contrato", str(exc))

    @app.get("/health")
    def health() -> dict[str, Any]:
        demos = len(list_demo_batches(settings.demo_dir))
        return {
            "status": "ok",
            "version": __version__,
            "auth_required": settings.api_token is not None,
            "demo_batches": demos,
            "mode": settings.mode,
            "capabilities": capabilities(settings, demos, settings_source is not None),
            "models": engine.models.json(),
            "admin": settings.admin_token_hash is not None,
        }

    @app.post("/desktop/focus", status_code=204)
    def focus(request: Request) -> Response:
        """Outra abertura do programa pede para trazer a janela desta instância para a frente."""
        secret = getattr(app.state, "focus_secret", None)
        handler = getattr(app.state, "focus_handler", None)
        given = request.headers.get("x-instance-secret", "")
        if settings.mode != "desktop" or not secret or not secrets.compare_digest(given, secret):
            raise HTTPException(404, "não encontrado")
        if handler is not None:
            handler()
        return Response(status_code=204)

    @app.post("/session/exchange")
    def exchange(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        if settings.mode != "desktop" or settings.api_token is None:
            raise HTTPException(404, "só existe no programa desktop")
        validate(body, "session-exchange-request.schema.json")
        if not engine.redeem_code(body["code"]):
            raise HTTPException(
                403, "código inválido, já usado ou vencido: abra o programa de novo"
            )
        return {"token": settings.api_token}

    @app.get("/session")
    def session() -> dict[str, Any]:
        if settings.mode == "desktop":
            return {"reviewer": os_user(), "machine": platform.node() or None, "source": "os"}
        return {"reviewer": None, "machine": None, "source": "none"}

    # Lotes -----------------------------------------------------------------

    @app.get("/batches")
    def list_batches() -> list[dict[str, Any]]:
        engine.purge()
        return [b.status_json() for b in engine.repo.list_batches()]

    @app.post("/batches", status_code=202)
    async def create_batch(
        files: Annotated[list[UploadFile], File()],
        profile_id: Annotated[str, Form()] = "demo",
        name: Annotated[str | None, Form()] = None,
        manifest: Annotated[UploadFile | None, File()] = None,
        numbering: Annotated[UploadFile | None, File()] = None,
    ) -> dict[str, Any]:
        require_models()
        profile = engine.profile(profile_id)
        batch_id = str(uuid.uuid4())
        root = engine.batch_dir(batch_id) / "input"
        root.mkdir(parents=True)
        limit = settings.max_upload_mb * 1024 * 1024
        try:
            written = 0
            raw = [safe_relative(f.filename or "") for f in files]
            names = strip_common_root(raw)
            folder = raw[0].parts[0] if names != raw else None
            for upload, rel in zip(files, names, strict=True):
                target = root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open("wb") as out:
                    while chunk := await upload.read(1 << 20):
                        written += len(chunk)
                        if written > limit:
                            raise UploadError("envio excede o limite configurado")
                        out.write(chunk)
            if len(names) == 1 and names[0].suffix.lower() == ".zip":
                archive = root / names[0]
                extract_zip(archive, root, limit)
                archive.unlink()
            if manifest is not None:
                (root / "manifest.csv").write_bytes(await manifest.read())
            if numbering is not None:
                data = json.loads(await numbering.read())
                validate(data, "numbering-sidecar.schema.json")
                (root / "numbering.json").write_text(json.dumps(data), encoding="utf-8")
        except (UploadError, json.JSONDecodeError) as exc:
            shutil.rmtree(root.parent, ignore_errors=True)
            status = 413 if "limite" in str(exc) else 400
            raise HTTPException(status, str(exc)) from exc
        except ContractError:
            shutil.rmtree(root.parent, ignore_errors=True)
            raise
        if folder is None and len(names) == 1 and names[0].suffix.lower() == ".zip":
            folder = names[0].stem
        return enqueue(batch_id, root, profile, name or folder or f"lote-{batch_id[:8]}")

    def require_models() -> None:
        if not engine.models.ok:
            raise HTTPException(
                503,
                "Análise bloqueada: "
                + "; ".join(engine.models.problems)
                + ". Reinstale o programa a partir do pacote original.",
            )

    def enqueue(
        batch_id: str,
        root: Path,
        profile: Profile,
        batch_name: str,
        source: str = "upload",
        station_id: str | None = None,
    ) -> dict[str, Any]:
        require_models()
        engine.repo.create_batch(batch_id, batch_name, profile.id, root, iso(engine.now()), source)
        engine.queue.submit(
            engine.analyze, batch_id, root, profile, batch_name, station_id, source == "local"
        )
        row = engine.repo.get_batch(batch_id)
        assert row is not None
        status: dict[str, Any] = row.status_json()
        return status

    @app.get("/demo-batches")
    def demo_batches() -> list[dict[str, Any]]:
        return [
            {"name": b.name, "pages": b.pages, "documents": b.documents}
            for b in list_demo_batches(settings.demo_dir)
        ]

    @app.post("/demo-batches/{name}", status_code=202)
    def start_demo_batch(
        name: str, body: Annotated[dict[str, Any] | None, Body()] = None
    ) -> dict[str, Any]:
        body = body or {}
        require_models()
        validate(body, "demo-batch-request.schema.json")
        profile = engine.profile(body.get("profile_id", "demo"))
        batch_id = str(uuid.uuid4())
        root = engine.batch_dir(batch_id) / "input"
        try:
            copy_demo_batch(settings.demo_dir, name, root)
        except LookupError as exc:
            shutil.rmtree(root.parent, ignore_errors=True)
            raise HTTPException(404, str(exc)) from exc
        return enqueue(batch_id, root, profile, name, source="demo")

    @app.post("/local-batches", status_code=202)
    def open_local(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        if settings.mode != "desktop":
            raise HTTPException(404, "lote por pasta só existe no programa desktop")
        require_models()
        validate(body, "local-batch-request.schema.json")
        default = "sos-piloto" if (settings.profiles_dir / "sos-piloto.yaml").is_file() else "demo"
        profile = engine.profile(body.get("profile_id", default))
        station_id = body.get("station_id")
        if station_id is not None and profile.station(station_id) is None:
            raise HTTPException(422, f"estação {station_id!r} não existe no perfil {profile.id!r}")
        batch = open_local_batch(
            engine.folder, body["path"], settings.allowed_roots, is_within, body.get("name")
        )
        return enqueue(str(uuid.uuid4()), batch.root, profile, batch.name, "local", station_id)

    def batch_or_404(batch_id: str) -> Any:
        row = engine.repo.get_batch(batch_id)
        if row is None:
            raise HTTPException(404, "lote não encontrado")
        return row

    def require_final(batch_id: str) -> None:
        """Corrigir tudo e salvar esperam a passada final (liberação por processo)."""
        if batch_or_404(batch_id).status != "analyzed":
            raise HTTPException(409, "espere a análise da caixa terminar")

    def report_or_409(batch_id: str) -> dict[str, Any]:
        batch_or_404(batch_id)
        report = engine.repo.get_report(batch_id)
        if report is None:
            raise HTTPException(409, "lote ainda não analisado")
        return report

    @app.get("/batches/{batch_id}")
    def get_batch(batch_id: str) -> dict[str, Any]:
        status: dict[str, Any] = batch_or_404(batch_id).status_json()
        return status

    @app.get("/batches/{batch_id}/events")
    async def batch_events(batch_id: str) -> StreamingResponse:
        batch_or_404(batch_id)

        async def stream() -> AsyncIterator[str]:
            last = None
            announced: set[str] = set()
            while True:
                row = engine.repo.get_batch(batch_id)
                if row is None:
                    return
                status = row.status_json()
                data = json.dumps(status, ensure_ascii=False)
                # Liberação por processo: um evento por processo que ficou pronto.
                ready = status.get("documents", {}).get("ready", [])
                for position, doc in enumerate(ready, start=1):
                    if doc["id"] in announced:
                        continue
                    announced.add(doc["id"])
                    event = {
                        **doc,
                        "ready": position,
                        "pending": len(status["documents"]["pending"]),
                    }
                    payload = json.dumps(event, ensure_ascii=False)
                    yield f"event: document_ready\ndata: {payload}\n\n"
                if data != last:
                    yield f"event: progress\ndata: {data}\n\n"
                    last = data
                if row.status in {"analyzed", "failed"}:
                    yield f"event: done\ndata: {data}\n\n"
                    return
                await asyncio.sleep(0.5)

        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/batches/{batch_id}/report")
    def get_report(batch_id: str) -> dict[str, Any]:
        return report_or_409(batch_id)

    @app.get("/batches/{batch_id}/findings")
    def list_findings(
        batch_id: str,
        severity: Annotated[list[str] | None, Query()] = None,
        rule: Annotated[list[str] | None, Query()] = None,
        pending: bool | None = None,
    ) -> list[dict[str, Any]]:
        report_or_409(batch_id)
        result = []
        for f in engine.repo.findings(batch_id):
            if severity and f["severity"] not in severity:
                continue
            if rule and f["rule"] not in rule:
                continue
            if pending is not None and finding_from_json(f).pending != pending:
                continue
            result.append(f)
        return result

    # Revisão -----------------------------------------------------------------

    def finding_batch(finding_id: str) -> str:
        found = engine.repo.get_finding(finding_id)
        if found is None:
            raise HTTPException(404, "sinalização não encontrada")
        return found[0]

    @app.post("/findings/{finding_id}/decision")
    def decide_finding(finding_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "decision-request.schema.json")
        batch_id = finding_batch(finding_id)
        ctx = engine.context(batch_id)
        result = engine.service.decide(
            ctx, finding_id, DecisionAction(body["action"]), body["reviewer"], body.get("note")
        )
        engine.collect_orientation(batch_id, ctx.profile, finding_id)
        return result

    @app.delete("/findings/{finding_id}/decision")
    def undo_decision(finding_id: str, reviewer: str = "revisor") -> dict[str, Any]:
        batch_id = finding_batch(finding_id)
        ctx = engine.context(batch_id)
        result = engine.service.undo(ctx, finding_id, reviewer)
        engine.collect_orientation(batch_id, ctx.profile, finding_id)
        return result

    # Correção em lote e lote corrigido -----------------------------------------------

    @app.post("/batches/{batch_id}/bulk-corrections", status_code=202)
    def start_bulk(batch_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "bulk-correction-request.schema.json")
        require_final(batch_id)
        ctx = engine.context(batch_id)
        operation = engine.service.start_bulk(
            ctx, body["scope"], body.get("document_id"), body["reviewer"]
        )
        engine.corrections.submit(engine.run_bulk, batch_id, operation["id"])
        return operation

    @app.get("/batches/{batch_id}/bulk-corrections")
    def list_bulk(batch_id: str) -> list[dict[str, Any]]:
        batch_or_404(batch_id)
        return engine.service.operations(batch_id)

    @app.get("/bulk-corrections/{operation_id}")
    def get_bulk(operation_id: str) -> dict[str, Any]:
        return engine.service.operation(operation_id)

    @app.delete("/bulk-corrections/{operation_id}")
    def undo_bulk(operation_id: str, reviewer: str) -> dict[str, Any]:
        operation = engine.service.operation(operation_id)
        return engine.service.undo_bulk(
            engine.context(operation["batch_id"]), operation_id, reviewer
        )

    @app.get("/batches/{batch_id}/corrected-plan")
    def corrected_plan(batch_id: str) -> dict[str, Any]:
        return engine.service.plan(engine.context(batch_id))

    @app.post("/batches/{batch_id}/corrected-batch", status_code=201)
    def save_corrected(batch_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "corrected-batch-request.schema.json")
        require_final(batch_id)
        ctx = engine.context(batch_id)
        destination = body.get("destination", "zip")
        writer: Callable[[datetime], Any]
        if destination == "folder":
            output = settings.output_root

            def writer(when: datetime) -> Any:
                return FolderTiffWriter(output, ctx.name, when)

        else:
            target = engine.batch_dir(batch_id) / "exports" / CORRECTED_ZIP

            def writer(when: datetime) -> Any:
                return ZipTiffWriter(target, when)

        saved = engine.service.save(
            ctx,
            body["reviewer"],
            writer,
            destination=destination,
            check_source=lambda: engine.source_changes(batch_id, ctx.root),
        )
        engine.generate_box_reports(batch_id, body["reviewer"])
        return saved

    @app.get("/batches/{batch_id}/box-reports")
    def list_box_reports(batch_id: str) -> list[dict[str, Any]]:
        batch_or_404(batch_id)
        return [
            {"id": item["id"], "report": item["report"]}
            for item in engine.repo.box_reports(batch_id)
        ]

    @app.post("/batches/{batch_id}/box-reports")
    def make_box_reports(
        batch_id: str, body: Annotated[dict[str, Any], Body()]
    ) -> list[dict[str, Any]]:
        reviewer = str(body.get("reviewer") or "").strip()
        if not reviewer:
            raise HTTPException(422, "reviewer é obrigatório")
        batch_or_404(batch_id)
        return engine.generate_box_reports(batch_id, reviewer)

    def management_reports() -> tuple[list[tuple[str, Mapping[str, Any]]], int, bool]:
        if settings.reports_dir is None:
            local = [(f"local:{rid}", rep) for rid, rep in engine.repo.all_box_reports()]
            return list(local), 0, False

        def valid(data: Any) -> bool:
            try:
                validate(data, "box-report.schema.json")
            except ContractError:
                return False
            return True

        found, skipped = SharedReportsFolder(settings.reports_dir).read(valid)
        return [(f"shared:{rel}", rep) for rel, rep in found], skipped, True

    @app.get("/management")
    def management(since: str | None = None, until: str | None = None) -> dict[str, Any]:
        for value in (since, until):
            if value:
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise HTTPException(422, f"data inválida: {value}") from exc
        reports, skipped, shared = management_reports()
        view = management_view(reports, since, until, skipped, shared)
        validate(view, "management.schema.json")
        return view

    @app.get("/management/report.pdf")
    def management_pdf(ref: str) -> Response:
        built: Mapping[str, Any] | None = None
        if ref.startswith("local:"):
            built = engine.repo.get_box_report(ref.removeprefix("local:"))
        elif ref.startswith("shared:") and settings.reports_dir is not None:
            path = SharedReportsFolder(settings.reports_dir).resolve(ref.removeprefix("shared:"))
            if path is not None:
                try:
                    data = json.loads(path.read_text("utf-8"))
                    validate(data, "box-report.schema.json")
                    built = data
                except (OSError, ValueError, ContractError):
                    built = None
        if built is None:
            raise HTTPException(404, "relatório não encontrado")
        name = f"{safe_name(built['box'])}-v{built['version']}.pdf"
        return Response(
            render_box_report_pdf(built),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/box-reports/{report_id}.pdf")
    def box_report_pdf(report_id: str) -> Response:
        built = engine.repo.get_box_report(report_id)
        if built is None:
            raise HTTPException(404, "relatório não encontrado")
        name = f"{safe_name(built['box'])}-v{built['version']}.pdf"
        return Response(
            render_box_report_pdf(built),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.post("/batches/{batch_id}/documents/{document_id}/pages", status_code=201)
    async def insert_document_page(
        batch_id: str,
        document_id: str,
        file: Annotated[UploadFile, File()],
        reviewer: Annotated[str, Form()],
        position: Annotated[int | None, Form()] = None,
    ) -> dict[str, Any]:
        if not reviewer.strip():
            raise HTTPException(422, "reviewer é obrigatório")
        data = await file.read()
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, "arquivo maior que o limite de envio")
        result = await asyncio.to_thread(
            engine.insert_complement,
            batch_id,
            document_id,
            file.filename or "folha.tif",
            data,
            position,
            reviewer.strip(),
        )
        validate(result, "page-insert-result.schema.json")
        return result

    @app.delete("/batches/{batch_id}/documents/{document_id}/pages/{page_id}")
    def delete_document_page(
        batch_id: str, document_id: str, page_id: str, reviewer: str = "revisor"
    ) -> dict[str, Any]:
        result = engine.remove_complement(batch_id, page_id, reviewer)
        if result["document"]["id"] != document_id:
            raise HTTPException(404, "a página não é deste processo")
        validate(result, "document-numbering.schema.json")
        return result

    @app.put("/pages/{page_id}/rotation")
    def put_rotation(page_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "rotation-request.schema.json")
        page = engine.repo.get_page(page_id)
        if page is None:
            raise HTTPException(404, "página não encontrada")
        ctx = engine.context(page["batch_id"])
        result = engine.service.set_rotation(ctx, page_id, int(body["angle_deg"]), body["reviewer"])
        engine.collect_orientation(page["batch_id"], ctx.profile, result["finding"]["id"])
        return result

    def apply_numbering(
        batch_id: str,
        reviewer: str,
        values: dict[str, str | None],
        document_id: str | None = None,
        order: list[str] | None = None,
    ) -> dict[str, Any]:
        """Valida, re-resolve e só então grava numeração digitada e ordem manual."""
        with engine.repo.locked():
            return _apply_numbering(batch_id, reviewer, values, document_id, order)

    def _apply_numbering(
        batch_id: str,
        reviewer: str,
        values: dict[str, str | None],
        document_id: str | None = None,
        order: list[str] | None = None,
    ) -> dict[str, Any]:
        row = batch_or_404(batch_id)
        profile = engine.batch_profile(batch_id, row.profile_id)
        report = report_or_409(batch_id)
        now = iso(engine.now())
        overrides = dict(engine.repo.numbering_overrides(batch_id))
        for page_id, value in values.items():
            if value is None:
                overrides.pop(page_id, None)
            else:
                overrides[page_id] = value
        orders = _orders(engine.repo.manual_orders(batch_id))
        if document_id is not None:
            if order is None:
                orders.pop(document_id, None)
            else:
                orders[document_id] = ManualOrder(tuple(order), reviewer, now)
        try:
            new = set_manual_numbering(report, profile, row.root, overrides, orders)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        before = {p["id"]: p.get("numbering") or {} for p in report["pages"]}
        for page_id, value in values.items():
            if value is None:
                engine.repo.clear_numbering(page_id)
            else:
                model = before.get(page_id, {})
                engine.repo.set_numbering(
                    page_id,
                    batch_id,
                    value,
                    reviewer,
                    now,
                    model.get("value") if "typed" not in model else None,
                    model.get("state") if "typed" not in model else None,
                )
        engine.collect_numbering(batch_id, profile, report, values, reviewer, now)
        if document_id is not None:
            engine.repo.set_manual_order(document_id, batch_id, order, reviewer, now)
        engine.repo.replace_report(batch_id, new)
        return new

    @app.put("/batches/{batch_id}/documents/{document_id}/numbering")
    def put_document_numbering(
        batch_id: str, document_id: str, body: Annotated[dict[str, Any], Body()]
    ) -> dict[str, Any]:
        validate(body, "document-numbering-update.schema.json")
        report = report_or_409(batch_id)
        doc = next((d for d in report["documents"] if d["id"] == document_id), None)
        if doc is None:
            raise HTTPException(404, "documento não encontrado neste lote")
        values = dict(body.get("values") or {})
        outside = [pid for pid in values if pid not in doc["page_ids"]]
        if outside:
            raise HTTPException(422, "página de outro documento: " + ", ".join(outside))
        if "order" in body:
            new = apply_numbering(batch_id, body["reviewer"], values, document_id, body["order"])
        else:
            new = apply_numbering(batch_id, body["reviewer"], values)
        new_doc = next(d for d in new["documents"] if d["id"] == document_id)
        ids = set(new_doc["page_ids"]) | {document_id}
        result = {
            "document": new_doc,
            "pages": {
                p["id"]: p["numbering"] for p in new["pages"] if p["id"] in ids and "numbering" in p
            },
            "findings": [
                f
                for f in new["findings"]
                if f["rule"] in SEQUENCE_RULES and f["target"]["id"] in ids
            ],
            "summary": new["batch"]["summary"],
        }
        validate(result, "document-numbering.schema.json")
        return result

    @app.put("/pages/{page_id}/numbering")
    def put_numbering(page_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "numbering-update.schema.json")
        page = engine.repo.get_page(page_id)
        if page is None:
            raise HTTPException(404, "página não encontrada")
        batch_id = page["batch_id"]
        new = apply_numbering(batch_id, body["reviewer"], {page_id: body["value"]})
        doc_pages = next(d["page_ids"] for d in new["documents"] if page_id in d["page_ids"])
        numbering = {
            p["id"]: p["numbering"]
            for p in new["pages"]
            if p["id"] in doc_pages and "numbering" in p
        }
        return {"pages": numbering, "summary": new["batch"]["summary"]}

    # Páginas, metadados e exportação -----------------------------------------------

    @app.get("/pages/{page_id}/image")
    def page_image(
        page_id: str, variant: str = "original", max_width: int | None = None
    ) -> Response:
        page = engine.repo.get_page(page_id)
        if page is None:
            raise HTTPException(404, "página não encontrada")
        row = batch_or_404(page["batch_id"])
        if variant == "corrected":
            corrected = engine.service.corrected_image(engine.context(row.id), page_id)
            if corrected is None:
                raise HTTPException(404, "página sem cópia corrigida")
            img = corrected
        elif variant == "original":
            source = page_path(row.root, engine.batch_dir(row.id), page["source_file"])
            img = engine.images.load_original(source, page["page_in_file"])
        else:
            raise HTTPException(422, "variant deve ser original ou corrected")
        if max_width and img.shape[1] > max_width:
            h = max(1, round(img.shape[0] * max_width / img.shape[1]))
            img = cv2.resize(img, (max_width, h), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png")

    @app.get("/pages/{page_id}/numbering-crop")
    def numbering_crop(page_id: str) -> Response:
        page = engine.repo.get_page(page_id)
        if page is None:
            raise HTTPException(404, "página não encontrada")
        path = engine.batch_dir(page["batch_id"]) / NUMBERING_CROPS / f"{page_id}.png"
        if not path.is_file():
            raise HTTPException(404, "página sem recorte de numeração")
        return Response(path.read_bytes(), media_type="image/png")

    @app.get("/documents/{document_id}/metadata")
    def document_metadata(document_id: str) -> list[dict[str, Any]]:
        batch_id = engine.repo.document_batch(document_id)
        if batch_id is None:
            raise HTTPException(404, "documento não encontrado")
        fields: list[dict[str, Any]] = report_or_409(batch_id)["metadata"][document_id]
        return fields

    @app.put("/documents/{document_id}/metadata/{name}")
    def put_metadata(
        document_id: str, name: str, body: Annotated[dict[str, Any], Body()]
    ) -> list[dict[str, Any]]:
        validate(body, "metadata-update.schema.json")
        batch_id = engine.repo.document_batch(document_id)
        if batch_id is None:
            raise HTTPException(404, "documento não encontrado")
        fields: list[dict[str, Any]] = report_or_409(batch_id)["metadata"][document_id]
        field = next((f for f in fields if f["name"] == name), None)
        if field is None:
            raise HTTPException(404, f"metadado {name!r} não existe neste documento")
        if "value" in body:
            field["value"] = body["value"]
            field["source"] = "reviewer"
            field["confidence"] = 1.0
        field["confirmed"] = True
        field["note"] = f"Confirmado por {body['reviewer']} em {iso(engine.now())}."
        validate(field, "metadata-field.schema.json")
        engine.repo.update_metadata(batch_id, document_id, fields)
        return fields

    @app.post("/batches/{batch_id}/exports", status_code=201)
    def create_exports(batch_id: str) -> dict[str, Any]:
        report = report_or_409(batch_id)
        out = engine.batch_dir(batch_id) / "exports"
        out.mkdir(parents=True, exist_ok=True)
        pages = {p["id"]: p for p in report["pages"]}
        contents = {
            "report.json": json.dumps(report, ensure_ascii=False, indent=2),
            "findings.csv": findings_csv(report["findings"], pages),
            "metadata.csv": metadata_csv(report),
            "rework_order.csv": rework_csv(report),
        }
        for name, text in contents.items():
            (out / name).write_text(text, encoding="utf-8")
        return {"files": list(contents)}

    @app.get("/batches/{batch_id}/exports/{name}")
    def get_export(batch_id: str, name: str) -> Response:
        batch_or_404(batch_id)
        path = engine.batch_dir(batch_id) / "exports" / name
        if name not in EXPORTS or not path.is_file():
            raise HTTPException(404, "exportação não encontrada; gere com POST .../exports")
        filename = f"{batch_or_404(batch_id).name}-{name}" if name == CORRECTED_ZIP else name
        return FileResponse(path, media_type=EXPORTS[name], filename=filename)

    # Perfis -----------------------------------------------------------------

    def source_or_404() -> SettingsSource:
        if settings_source is None:
            raise HTTPException(404, "configuração pela tela só existe no programa desktop")
        return settings_source

    restart = {"required": False}

    @app.get("/settings")
    def get_settings() -> dict[str, Any]:
        return settings_view(source_or_404().load(), restart["required"])

    @app.put("/settings")
    def put_settings(body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        source = source_or_404()
        validate(body, "settings-update.schema.json")
        changes = dict(body.get("changes") or {})
        reset = list(body.get("reset") or [])
        refused = sorted((set(changes) | set(reset)) - set(USER_EDITABLE))
        if refused:
            raise SettingsError(
                [
                    SettingsProblem(
                        k, "tela de configurações", "chave editável pela tela", changes.get(k)
                    )
                    for k in refused
                ]
            )
        resolved = source.save_user(changes, reset)
        restart["required"] = True
        log.info("configuração do usuário alterada: %s", sorted(set(changes) | set(reset)))
        return settings_view(resolved, True)

    # Diagnóstico ---------------------------------------------------------------------

    @app.post("/diagnostics/client-errors", status_code=204)
    def client_error(body: Annotated[dict[str, Any], Body()]) -> Response:
        validate(body, "client-error.schema.json")
        user = os_user() if settings.mode == "desktop" else None
        engine.record(record_from_client(body, version=__version__, user=user))
        return Response(status_code=204)

    def require_admin(request: Request) -> str:
        """Confere ``X-Admin-Token``; devolve quem é (para o histórico)."""
        if settings.admin_token_hash is None:
            raise HTTPException(404, "área de administração desligada neste computador")
        wait = engine.admin_attempts.blocked_for()
        if wait > 0:
            raise HTTPException(429, f"tentativas demais; espere {wait:.0f} s")
        given = request.headers.get("x-admin-token", "")
        if not given or not verify_token(given, settings.admin_token_hash):
            engine.admin_attempts.failure()
            raise HTTPException(401, "token de administrador inválido")
        engine.admin_attempts.success()
        return os_user() if settings.mode == "desktop" else "administrador"

    def diagnostic_filters(
        version: str | None, machine: str | None, severity: str | None, origin: str | None
    ) -> dict[str, str | None]:
        return {"version": version, "machine": machine, "severity": severity, "origin": origin}

    @app.get("/admin/diagnostics")
    def list_diagnostics(
        request: Request,
        version: str | None = None,
        machine: str | None = None,
        severity: str | None = None,
        origin: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        require_admin(request)
        records = filtered(
            engine.all_diagnostics(), diagnostic_filters(version, machine, severity, origin)
        )
        grouped = groups(records, engine.repo.diagnostic_resolutions())
        everything = engine.all_diagnostics()
        return {
            "summary": diagnostics_summary(records, grouped, engine.now()),
            "groups": [g for g in grouped if status is None or g["status"] == status],
            "filters": {
                "versions": sorted({r["version"] for r in everything}),
                "machines": sorted({r["machine"] for r in everything}),
            },
        }

    @app.get("/admin/diagnostics/export")
    def export_diagnostics(request: Request) -> Response:
        require_admin(request)
        records = engine.all_diagnostics()
        grouped = groups(records, engine.repo.diagnostic_resolutions())
        view = settings_view(settings_source.load(), False) if settings_source else {}
        data = export_package(records, grouped, view, __version__, engine.now())
        name = f"diagnostico-qa-{engine.now():%Y%m%d-%H%M%S}.zip"
        return Response(
            data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}"'},
        )

    @app.get("/admin/diagnostics/{signature}")
    def diagnostic_detail(request: Request, signature: str) -> dict[str, Any]:
        require_admin(request)
        records = [r for r in engine.all_diagnostics() if r["signature"] == signature]
        if not records:
            raise HTTPException(404, "erro não encontrado")
        (group,) = groups(records, engine.repo.diagnostic_resolutions())
        return {"group": group, "occurrences": records[-200:]}

    @app.post("/admin/diagnostics/{signature}/resolve")
    def resolve_diagnostic(request: Request, signature: str) -> dict[str, Any]:
        who = require_admin(request)
        if not any(r["signature"] == signature for r in engine.all_diagnostics()):
            raise HTTPException(404, "erro não encontrado")
        engine.repo.resolve_diagnostic(signature, who, iso(engine.now()))
        return diagnostic_detail(request, signature)

    @app.get("/profiles/{profile_id}/rules")
    def profile_rules(profile_id: str, station_id: str | None = None) -> list[dict[str, Any]]:
        profile = engine.profile(profile_id)
        if station_id is not None and profile.station(station_id) is None:
            raise HTTPException(404, f"estação {station_id!r} não existe no perfil")
        return profile.effective_rules(station_id)

    @app.get("/profiles")
    def list_profiles() -> list[dict[str, Any]]:
        return [dict(load_profile(p).raw) for p in sorted(settings.profiles_dir.glob("*.yaml"))]

    @app.get("/profiles/{profile_id}")
    def get_profile(profile_id: str) -> dict[str, Any]:
        return dict(engine.profile(profile_id).raw)

    @app.put("/profiles/{profile_id}")
    def put_profile(profile_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        if body.get("id") != profile_id:
            raise HTTPException(422, "o id do corpo deve ser igual ao da rota")
        try:
            profile = profile_from_dict(body)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        path = settings.profiles_dir / f"{profile.id}.yaml"
        path.write_text(yaml.safe_dump(body, allow_unicode=True, sort_keys=False), "utf-8")
        return dict(profile.raw)

    # Interface na mesma origem: sem CORS e sem VITE_API_URL (ADR-0010). Montada por
    # último, só atende o que nenhuma rota da API atendeu.
    if settings.ui_dir is not None and (settings.ui_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=settings.ui_dir, html=True), name="ui")

    return app
