"""Aplicação FastAPI. Rotas e formatos seguem ``contracts/openapi.yaml``.

Corpos de requisição e de resposta são validados contra os JSON Schemas do
contrato (``application.contracts``), em vez de modelos escritos à mão.
"""

from __future__ import annotations

import asyncio
import io
import json
import logging
import shutil
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

import cv2
import numpy as np
import yaml
from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response, StreamingResponse
from PIL import Image

from qa_engine import __version__
from qa_engine.adapters.images import FileImageSource
from qa_engine.adapters.sqlite import SqliteRepository
from qa_engine.application.contracts import ContractError, validate
from qa_engine.application.corrections import (
    IMAGE_ACTIONS,
    CorrectionNotApplicableError,
    apply_correction,
)
from qa_engine.application.exports import findings_csv, metadata_csv, rework_csv
from qa_engine.application.profile import Profile, load_profile, profile_from_dict
from qa_engine.application.review import (
    baselines_from_json,
    baselines_json,
    decide,
    finding_from_json,
    recompute_summary,
    renumber,
)
from qa_engine.application.serialize import analysis_json, iso
from qa_engine.application.services import run_analysis
from qa_engine.domain.model import CorrectionAction, CorrectionClass, DecisionAction
from qa_engine.entrypoints.http.settings import Settings
from qa_engine.entrypoints.http.uploads import (
    UploadError,
    extract_zip,
    safe_relative,
    strip_common_root,
)

log = logging.getLogger("qa_engine.http")
EXPORTS = {
    "report.json": "application/json",
    "findings.csv": "text/csv; charset=utf-8",
    "metadata.csv": "text/csv; charset=utf-8",
    "rework_order.csv": "text/csv; charset=utf-8",
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
        self.images = FileImageSource()

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

    def purge(self) -> None:
        """Apaga lotes mais antigos que a retenção (24 h na PoC)."""
        cutoff = iso(self.now() - timedelta(hours=self.settings.retention_hours))
        for root in self.repo.purge_before(cutoff):
            shutil.rmtree(root.parent if root.name == "input" else root, ignore_errors=True)

    def analyze(self, batch_id: str, root: Path, profile: Profile, name: str) -> None:
        """Trabalho de fundo: analisa e grava o resultado."""
        try:
            analysis = run_analysis(
                root,
                profile,
                workers=self.settings.workers,
                name=name,
                batch_id=batch_id,
                progress=lambda done, total: self.repo.set_progress(batch_id, done, total),
            )
            report = analysis_json(analysis)
            validate(report, "analysis.schema.json")
            (self.batch_dir(batch_id) / "baselines.json").write_text(
                json.dumps(baselines_json(analysis.baselines)), encoding="utf-8"
            )
            self.repo.save_report(batch_id, report)
        except Exception as exc:
            log.exception("falha na análise do lote %s", batch_id)
            self.repo.fail(batch_id, f"{exc.__class__.__name__}: {exc}"[:500])


def create_app(settings: Settings | None = None) -> FastAPI:
    """Monta a aplicação."""
    settings = settings or Settings.from_env()
    engine = Engine(settings)
    if settings.api_token is None:
        log.warning("QA_API_TOKEN não definido: API sem autenticação (só desenvolvimento)")

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        engine.purge()
        yield
        engine.queue.shutdown(wait=False, cancel_futures=True)
        engine.repo.close()

    app = FastAPI(
        title="QA Automático de Digitalização",
        version=__version__,
        lifespan=lifespan,
        docs_url="/docs",
        openapi_url="/openapi.json",
    )
    app.state.engine = engine
    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(settings.cors_origins),
            allow_methods=["GET", "POST", "PUT", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )

    @app.middleware("http")
    async def auth(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        public = request.url.path in {"/health", "/docs", "/openapi.json"}
        if settings.api_token and not public and request.method != "OPTIONS":
            header = request.headers.get("authorization", "")
            if header != f"Bearer {settings.api_token}":
                return problem(401, "Não autorizado", "Envie Authorization: Bearer <token>.")
        return await call_next(request)

    @app.exception_handler(HTTPException)
    async def http_error(_: Request, exc: HTTPException) -> JSONResponse:
        return problem(exc.status_code, str(exc.detail))

    @app.exception_handler(ContractError)
    async def contract_error(_: Request, exc: ContractError) -> JSONResponse:
        return problem(422, "Documento fora do contrato", str(exc))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

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
        batch_name = name or folder or f"lote-{batch_id[:8]}"
        engine.repo.create_batch(batch_id, batch_name, profile.id, root, iso(engine.now()))
        engine.queue.submit(engine.analyze, batch_id, root, profile, batch_name)
        row = engine.repo.get_batch(batch_id)
        assert row is not None
        return row.status_json()

    def batch_or_404(batch_id: str) -> Any:
        row = engine.repo.get_batch(batch_id)
        if row is None:
            raise HTTPException(404, "lote não encontrado")
        return row

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
            while True:
                row = engine.repo.get_batch(batch_id)
                if row is None:
                    return
                data = json.dumps(row.status_json(), ensure_ascii=False)
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

    @app.post("/findings/{finding_id}/decision")
    def decide_finding(finding_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "decision-request.schema.json")
        found = engine.repo.get_finding(finding_id)
        if found is None:
            raise HTTPException(404, "sinalização não encontrada")
        batch_id, finding = found
        row = batch_or_404(batch_id)
        profile = engine.profile(row.profile_id)
        action = DecisionAction(body["action"])
        applied: dict[str, Any] | None = None
        correction = finding["correction"]
        image_fix = (
            correction["kind"] == CorrectionClass.AUTOMATIC.value
            and CorrectionAction(correction["action"]) in IMAGE_ACTIONS
            and finding["target"]["kind"] == "page"
        )
        if action is DecisionAction.CORRECT and image_fix:
            applied = _apply(engine, batch_id, finding, profile)
        updated = decide(finding, action, body["reviewer"], engine.now(), body.get("note"))
        report = engine.repo.get_report(batch_id)
        assert report is not None
        report["findings"] = [updated if f["id"] == finding_id else f for f in report["findings"]]
        summary = recompute_summary(report, profile)
        engine.repo.record_decision(batch_id, updated, summary)
        response: dict[str, Any] = {"finding": updated, "summary": summary}
        if applied is not None:
            response["applied"] = applied
        return response

    @app.delete("/findings/{finding_id}/decision")
    def undo_decision(finding_id: str, reviewer: str = "revisor") -> dict[str, Any]:
        found = engine.repo.get_finding(finding_id)
        if found is None:
            raise HTTPException(404, "sinalização não encontrada")
        batch_id, finding = found
        if not finding.get("decision"):
            raise HTTPException(409, "a sinalização não tem decisão para desfazer")
        row = batch_or_404(batch_id)
        profile = engine.profile(row.profile_id)
        updated = {k: v for k, v in finding.items() if k != "decision"}
        report = engine.repo.get_report(batch_id)
        assert report is not None
        report["findings"] = [updated if f["id"] == finding_id else f for f in report["findings"]]
        summary = recompute_summary(report, profile)
        engine.repo.undo_decision(batch_id, updated, reviewer, iso(engine.now()), summary)
        return {"finding": updated, "summary": summary}

    @app.put("/pages/{page_id}/numbering")
    def put_numbering(page_id: str, body: Annotated[dict[str, Any], Body()]) -> dict[str, Any]:
        validate(body, "numbering-update.schema.json")
        page = engine.repo.get_page(page_id)
        if page is None:
            raise HTTPException(404, "página não encontrada")
        batch_id = page["batch_id"]
        row = batch_or_404(batch_id)
        profile = engine.profile(row.profile_id)
        report = report_or_409(batch_id)
        overrides = dict(engine.repo.numbering_overrides(batch_id))
        overrides[page_id] = body["value"]
        try:
            new = renumber(report, profile, row.root, overrides)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        engine.repo.set_numbering(
            page_id, batch_id, body["value"], body["reviewer"], iso(engine.now())
        )
        engine.repo.replace_report(batch_id, new)
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
            corrected = sorted((engine.batch_dir(row.id) / "corrected").glob(f"{page_id}.*.png"))
            if not corrected:
                raise HTTPException(404, "página sem cópia corrigida")
            img = np.asarray(Image.open(corrected[-1]))
        elif variant == "original":
            img = engine.images.load_original(row.root / page["source_file"], page["page_in_file"])
        else:
            raise HTTPException(422, "variant deve ser original ou corrected")
        if max_width and img.shape[1] > max_width:
            h = max(1, round(img.shape[0] * max_width / img.shape[1]))
            img = cv2.resize(img, (max_width, h), interpolation=cv2.INTER_AREA)
        buf = io.BytesIO()
        Image.fromarray(img).save(buf, format="PNG")
        return Response(buf.getvalue(), media_type="image/png")

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
        return PlainTextResponse(path.read_text("utf-8"), media_type=EXPORTS[name])

    # Perfis -----------------------------------------------------------------

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

    return app


def _apply(
    engine: Engine, batch_id: str, finding: dict[str, Any], profile: Profile
) -> dict[str, Any]:
    page = engine.repo.get_page(finding["target"]["id"])
    row = engine.repo.get_batch(batch_id)
    if page is None or row is None:
        raise HTTPException(404, "página não encontrada")
    baselines_path = engine.batch_dir(batch_id) / "baselines.json"
    baselines = (
        baselines_from_json(json.loads(baselines_path.read_text("utf-8")))
        if baselines_path.is_file()
        else {}
    )
    original = engine.images.load_original(row.root / page["source_file"], page["page_in_file"])
    sha = next(
        (
            p["sha256"]
            for p in (engine.repo.get_report(batch_id) or {"pages": []})["pages"]
            if p["id"] == page["id"]
        ),
        "",
    )
    try:
        record = apply_correction(
            finding=finding_from_json(finding),
            original=original,
            dpi=page["dpi"],
            source_sha256=sha,
            out_dir=engine.batch_dir(batch_id) / "corrected",
            profile=profile,
            baselines=baselines,
            now=engine.now(),
        )
    except CorrectionNotApplicableError as exc:
        raise HTTPException(422, str(exc)) from exc
    return {
        "output": record.output.name,
        "output_sha256": record.output_sha256,
        "remaining_rules": list(record.remaining_rules),
    }
