"""Caso de uso AnalyzeBatch: do diretório do lote ao veredito (``docs/arquitetura/index.md``)."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np

from qa_engine.adapters.metadata import LOSSY_COMPRESSIONS
from qa_engine.application.layout import DocumentLayout, discover, read_manifest
from qa_engine.application.metadata import MetadataField, document_metadata, match_station
from qa_engine.application.numbering_image import DEFAULT_CONFUSIONS, ImageNumberingReader
from qa_engine.application.profile import NumberingImageConfig, Profile
from qa_engine.detectors import (
    black_borders,
    blank_page,
    corrupted_file,
    duplicate_page,
    orientation,
    sequence,
    skew,
)
from qa_engine.detectors.base import (
    ANALYSIS_DPI,
    Flag,
    Observation,
    PageFeatures,
    PageRaster,
    Stats,
    baseline_of,
)
from qa_engine.detectors.features import compute_features
from qa_engine.detectors.registry import PAGE_DETECTORS, manifest, params_for
from qa_engine.domain import ids
from qa_engine.domain.model import (
    Document,
    DocumentState,
    Finding,
    Page,
    Severity,
    Target,
    TargetKind,
    Verdict,
)
from qa_engine.domain.scoring import (
    batch_verdict,
    document_state,
    findings_by_document,
    green_sample,
    pages_needing_review,
)
from qa_engine.domain.sequencing import Mark, PageCandidates, PageNumbering, parse_folio
from qa_engine.ports import (
    Clock,
    Executor,
    FileMetadata,
    ImageSource,
    LoadError,
    MetadataReader,
    NumberingReader,
    OrientationClassifier,
)

ProgressCallback = Callable[[int, int], None]


@dataclass(frozen=True, slots=True)
class PageTask:
    """Trabalho de um processo: analisar uma página."""

    path: Path
    page_in_file: int
    rules: tuple[tuple[str, Mapping[str, Any]], ...]
    duplicate_min_ink: float
    models_dir: Path | None = None
    """Modelos embarcados; sem eles, a orientação não é classificada."""
    numbering: NumberingImageConfig | None = None
    """Ler a numeração da imagem (sem ``numbering.json`` no lote e com modelos)."""
    blank_corners: NumberingImageConfig | None = None
    """Em página quase vazia, procurar escrito nos quatro cantos (com modelos)."""


@dataclass(frozen=True, slots=True)
class PageResult:
    """Resultado de :func:`analyze_page`."""

    width_px: int = 0
    height_px: int = 0
    dpi: float | None = None
    color_mode: Any = None
    scale: float = 1.0
    observations: Mapping[str, Observation] = field(default_factory=dict)
    fingerprint: tuple[int, Any, float, bool, bytes, bytes, str | None] | None = None
    error: str | None = None
    marks: tuple[Mark, ...] = ()
    """Marcas de numeração lidas da imagem."""
    numbering_crop: bytes | None = None
    """Recorte da região da numeração (PNG), para a tela de Sequência."""
    written: bool = False
    """Algum escrito com tinta na região da numeração (mesmo ilegível)."""
    faint: bool = False
    """Só traço fraco, sem tinta, na numeração ou nos cantos: branca vai para revisão."""


def _classifier(models_dir: Path) -> OrientationClassifier:
    """Classificador de orientação do processo (carregado uma vez por processo)."""
    from qa_engine.adapters.orientation import PaddleOrientationClassifier

    key = models_dir.resolve()
    if key not in _CLASSIFIERS:
        _CLASSIFIERS[key] = PaddleOrientationClassifier(key)
    return _CLASSIFIERS[key]


_CLASSIFIERS: dict[Path, OrientationClassifier] = {}
_READERS: dict[
    tuple[Path, str, float, float, tuple[tuple[str, str, float], ...]], ImageNumberingReader
] = {}


def _reader(models_dir: Path, config: NumberingImageConfig) -> ImageNumberingReader:
    """Leitor de numeração do processo (modelos carregados uma vez por processo)."""
    from qa_engine.adapters.text_detection import OpenCvTextDetector, PaddleTextDetector
    from qa_engine.adapters.text_recognition import recognizer_by_name

    key = (
        models_dir.resolve(),
        config.recognizer,
        config.struck_threshold,
        config.min_height_mm,
        config.confusions,
    )
    if key not in _READERS:
        _READERS[key] = ImageNumberingReader(
            PaddleTextDetector(key[0]),
            recognizer_by_name(key[0], config.recognizer),
            struck_threshold=config.struck_threshold,
            min_height_mm=config.min_height_mm,
            fallback=OpenCvTextDetector(),
            confusions=config.confusions or DEFAULT_CONFUSIONS,
        )
    return _READERS[key]


ORIENTED_RULES = frozenset({"skew"})
"""Regras que dependem do sentido do texto: medidas na vista de conteúdo já orientada."""
CONTENT_RULES = frozenset({"blur", "exposure"})
"""Regras que medem o conteúdo: na vista sem as faixas pretas do digitalizador."""
CONTENT_SLACK = 0.005
"""Folga, em fração do lado, cortada além de cada faixa preta na vista de conteúdo."""


def content_view(
    raster: PageRaster, features: PageFeatures, params: Mapping[str, Any] | None
) -> tuple[PageRaster, PageFeatures]:
    """A página sem as faixas pretas que ``black_borders`` mede, com folga (ADR-0027).

    A faixa preta derruba a nitidez medida, puxa a mediana da tinta e entra no recorte que o
    classificador de orientação vê. Sem faixa, a vista é a própria página.
    """
    p = dict(params) if params is not None else params_for(black_borders.ID, None)
    obs = black_borders.DETECTOR.measure(raster, features, p)
    crop = dict(obs.extra.get("crop_fraction", {}))
    # Só a faixa que a regra sinalizaria: cortar uma linha escura da borda do scanner muda o
    # recorte central do classificador sem tirar nada que atrapalhe as medidas.
    floor = float(p["min_fraction"])
    if not any(float(v) > floor for v in crop.values()):
        return raster, features
    h, w = raster.gray.shape

    def cut(side: str, size: int) -> int:
        frac = float(crop.get(side, 0.0))
        return math.ceil((frac + CONTENT_SLACK) * size) if frac > floor else 0

    top, bottom, left, right = cut("top", h), cut("bottom", h), cut("left", w), cut("right", w)
    if top + bottom >= h // 2 or left + right >= w // 2:
        return raster, features
    gray = np.ascontiguousarray(raster.gray[top : h - bottom, left : w - right])
    return replace(raster, gray=gray), compute_features(gray)


def oriented_view(gray: Any, angle: int) -> Any:
    """Vista em memória girada para ficar de pé (o arquivo original não é tocado)."""
    turns = {90: 1, 180: 2, 270: 3}  # np.rot90 gira anti-horário: desfaz o giro horário
    return np.ascontiguousarray(np.rot90(gray, turns[angle])) if angle in turns else gray


def analyze_page(
    task: PageTask,
    source: ImageSource | None = None,
    classifier: OrientationClassifier | None = None,
) -> PageResult:
    """Decodifica uma página e calcula as medidas de cada detector ligado (função de processo).

    Com a regra ``orientation`` ligada e os modelos disponíveis, classifica a orientação e,
    se a página estiver de lado ou de cabeça para baixo com probabilidade de pelo menos
    ``review_threshold``, mede as regras que dependem do sentido do texto (inclinação)
    numa vista girada em memória. As demais regras medem a imagem original.
    """
    if source is None:
        from qa_engine.adapters.images import FileImageSource

        source = FileImageSource()
    try:
        loaded = source.load(task.path, task.page_in_file, ANALYSIS_DPI)
    except LoadError as exc:
        return PageResult(error=str(exc))
    raster = PageRaster(
        loaded.gray, loaded.scale, loaded.dpi, loaded.color_mode, loaded.mean_saturation
    )
    features = compute_features(raster.gray)
    rules = dict(task.rules)
    content, content_features = content_view(raster, features, rules.get(black_borders.ID))
    upright_raster, upright_features = content, content_features
    page_upright = raster.gray  # numeração: a página inteira, de pé (regiões são frações dela)
    rotated = False
    pre_skew: Observation | None = None
    if orientation.ID in rules and not orientation.skips(features, rules[orientation.ID]):
        if classifier is None and task.models_dir is not None:
            classifier = _classifier(task.models_dir)
        if classifier is not None:
            orient_params = rules[orientation.ID]
            skew_params = rules.get(skew.ID) or params_for(skew.ID, None)
            # Inclinação na vista de conteúdo antes de classificar: com inclinação forte e
            # confiável, o classificador recebe uma cópia endireitada (ADR-0027).
            pre_skew = skew.DETECTOR.measure(content, content_features, skew_params)
            prediction = classifier.classify(content.gray)
            if pre_skew.eligible:
                angle = float(pre_skew.values["angle"])
                strong = abs(angle) > float(orient_params["deskew_before_orient"])
                trusted = float(pre_skew.extra.get("confidence", 0.0)) >= float(
                    orient_params["deskew_min_confidence"]
                )
                if strong and trusted:
                    # O classificador olha um recorte central e é sensível a ele: vale a
                    # leitura mais confiante entre a vista crua e a endireitada.
                    other = classifier.classify(skew.straightened(content.gray, angle))
                    if other.probability > prediction.probability:
                        prediction = other
            raster = replace(raster, orientation=prediction)
            content = replace(content, orientation=prediction)
            upright_raster = content
            review_at = orientation.suggest_at(features, rules[orientation.ID])
            if prediction.angle and prediction.probability >= review_at:
                turned = oriented_view(content.gray, prediction.angle)
                upright_raster = replace(content, gray=turned)
                upright_features = compute_features(turned)
                page_upright = oriented_view(raster.gray, prediction.angle)
                rotated = True
    detectors = {d.id: d for d in PAGE_DETECTORS}
    observations = {}
    for rule, params in task.rules:
        if rule == skew.ID and pre_skew is not None and not rotated:
            observations[rule] = pre_skew  # de pé: a medida antes da orientação vale
        elif rule in ORIENTED_RULES:
            observations[rule] = detectors[rule].measure(upright_raster, upright_features, params)
        elif rule in CONTENT_RULES:
            observations[rule] = detectors[rule].measure(content, content_features, params)
        else:
            observations[rule] = detectors[rule].measure(raster, features, params)
    blank_params = rules.get(blank_page.ID)
    numbering_read = None
    if task.numbering is not None and task.models_dir is not None:
        numbering_read = _reader(task.models_dir, task.numbering).read(
            page_upright,
            ANALYSIS_DPI,
            task.numbering.regions,
            ink=blank_page.ink_check(features.paper_level, blank_params),
        )
    written = numbering_read.written if numbering_read else False
    faint = numbering_read.faint if numbering_read else False
    if (
        not written
        and blank_params is not None
        and task.blank_corners is not None
        and task.models_dir is not None
        and features.ink_coverage < float(blank_params["near_blank_threshold"])
    ):
        # Página quase vazia: a orientação não é confiável, então procura nos quatro cantos.
        written, corner_faint = _reader(task.models_dir, task.blank_corners).corner_writing(
            raster.gray, ANALYSIS_DPI, blank_page.ink_check(features.paper_level, blank_params)
        )
        faint = faint or corner_faint
    blur_obs = observations.get("blur")
    sharpness = blur_obs.values["energy"] if blur_obs is not None else 0.0
    view_png, ink_png = duplicate_page.views(raster.gray, features.ink)
    blank_at = float(blank_params["blank_threshold"]) if blank_params is not None else 0.003
    fingerprint = (
        duplicate_page.dhash(raster.gray),
        duplicate_page.thumbnail(raster.gray),
        0.0 if math.isnan(sharpness) else sharpness,
        features.ink_coverage >= task.duplicate_min_ink,
        view_png,
        ink_png,
        duplicate_page.raster_hash(raster.gray) if features.ink_coverage >= blank_at else None,
    )
    return PageResult(
        loaded.width_px,
        loaded.height_px,
        loaded.dpi,
        loaded.color_mode,
        loaded.scale,
        observations,
        fingerprint,
        marks=numbering_read.marks if numbering_read else (),
        numbering_crop=numbering_read.crop_png if numbering_read else None,
        written=written,
        faint=faint and not written,
    )


@dataclass(frozen=True, slots=True)
class BatchSummary:
    """Painel do lote (tela 3)."""

    verdict: Verdict
    pages_total: int
    pages_without_review: int
    documents_total: int
    document_states: Mapping[str, DocumentState]
    by_severity: Mapping[str, int]
    by_rule: Mapping[str, int]
    by_station: Mapping[str, int]
    green_sample: tuple[str, ...]
    review_pages: tuple[str, ...]
    lossy_files: tuple[str, ...]

    @property
    def no_review_ratio(self) -> float:
        """Fração das páginas que dispensam revisão humana (meta: 50% ou mais)."""
        return self.pages_without_review / self.pages_total if self.pages_total else 0.0


@dataclass(frozen=True, slots=True)
class BatchAnalysis:
    """Resultado completo da análise de um lote."""

    batch_id: str
    name: str
    profile_id: str
    analyzed_at: datetime
    root: Path
    documents: tuple[Document, ...]
    pages: tuple[Page, ...]
    findings: tuple[Finding, ...]
    numbering: Mapping[str, PageNumbering]
    proposed_order: Mapping[str, tuple[str, ...]]
    metadata: Mapping[str, tuple[MetadataField, ...]]
    files: Mapping[str, FileMetadata]
    stations: Mapping[str, str]
    """Local da estação por página (para a ordem de retrabalho)."""
    summary: BatchSummary
    engine_version: str
    baselines: Mapping[str, Mapping[str, Stats]] = field(default_factory=dict)
    """Linha de base de cada detector, usada para reanalisar cópias corrigidas."""
    marks: Mapping[str, tuple[Mark, ...]] = field(default_factory=dict)
    """Marcas de numeração de cada página, como o resolvedor as recebeu."""
    numbering_source: str = "none"
    """``sidecar`` (numbering.json), ``image`` (lidas da imagem) ou ``none``."""
    numbering_crops: Mapping[str, bytes] = field(default_factory=dict)
    """Recorte da região da numeração por página (PNG)."""
    station_ids: Mapping[str, str | None] = field(default_factory=dict)
    """Identificador da estação por página: define os ajustes de regra aplicados a ela."""
    final: bool = True
    """Passada final (lote inteiro); falso no relatório parcial de processos prontos."""
    pending_documents: tuple[tuple[str, str], ...] = ()
    """Processos ainda não prontos (identificador, nome), na ordem do lote."""


DocumentCallback = Callable[[BatchAnalysis, str], None]
"""Liberação por processo: relatório parcial e o documento que acabou de ficar pronto."""


def _content_key(files: Mapping[str, FileMetadata]) -> str:
    digest = hashlib.sha256()
    for rel in sorted(files):
        digest.update(f"{rel}\0{files[rel].sha256}\n".encode())
    return digest.hexdigest()


def summarize(
    *,
    batch_id: str,
    profile: Profile,
    documents: Sequence[Document],
    pages: Sequence[Page],
    findings: Sequence[Finding],
    stations: Mapping[str, str],
    lossy_files: Sequence[str] = (),
) -> BatchSummary:
    """Recalcula estados, veredito e métricas (também após cada decisão do revisor)."""
    page_to_doc = {p.id: p.document_id for p in pages}
    grouped = findings_by_document(findings, page_to_doc)
    states = {d.id: document_state(grouped.get(d.id, [])) for d in documents}
    greens = [d for d, s in states.items() if s is DocumentState.GREEN]
    sample = green_sample(batch_id, greens, profile.verdict.green_sample_ratio)
    review = pages_needing_review([p.id for p in pages], findings, page_to_doc, sample)
    by_station: Counter[str] = Counter()
    for f in findings:
        if f.target.kind is TargetKind.PAGE and f.severity.rank >= Severity.MEDIUM.rank:
            by_station[stations.get(f.target.id, "não identificada")] += 1
    return BatchSummary(
        verdict=batch_verdict(states, findings, profile.verdict),
        pages_total=len(pages),
        pages_without_review=len(pages) - len(review),
        documents_total=len(documents),
        document_states=states,
        by_severity={s.value: sum(f.severity is s for f in findings) for s in Severity},
        by_rule=dict(sorted(Counter(f.rule for f in findings).items())),
        by_station=dict(sorted(by_station.items())),
        green_sample=tuple(sample),
        review_pages=tuple(sorted(review)),
        lossy_files=tuple(lossy_files),
    )


class _FindingFactory:
    def __init__(self, batch_id: str, profile: Profile) -> None:
        self.batch_id = batch_id
        self.profile = profile
        self.counter: Counter[tuple[str, str]] = Counter()
        self.findings: list[Finding] = []

    def add(self, rule: str, target: Target, flag: Flag, scale: float = 1.0) -> None:
        ordinal = self.counter[(target.id, rule)]
        self.counter[(target.id, rule)] += 1
        region = flag.region.scaled(1.0 / scale) if flag.region is not None else None
        self.findings.append(
            Finding(
                id=ids.finding_id(self.batch_id, target.id, rule, ordinal),
                target=target,
                rule=rule,
                rule_version=manifest(rule).version,
                severity=self.profile.severity_override(rule) or flag.severity,
                measure=_finite(flag.measure),
                threshold=_finite(flag.threshold),
                confidence=round(flag.confidence, 4),
                correction=flag.correction,
                message=flag.message,
                region=region,
            )
        )


def _finite(value: float) -> float:
    return float(value) if math.isfinite(value) else 0.0


def analyze_batch(
    root: Path,
    profile: Profile,
    *,
    image_source: ImageSource,
    metadata_reader: MetadataReader,
    numbering_reader: NumberingReader,
    executor: Executor,
    clock: Clock,
    name: str | None = None,
    batch_id: str | None = None,
    progress: ProgressCallback | None = None,
    engine_version: str = "0.1.0",
    fallback_station: str | None = None,
    models_dir: Path | None = None,
    on_document: DocumentCallback | None = None,
) -> BatchAnalysis:
    """Analisa um lote local: página, documento e lote, nessa ordem.

    Args:
        root: pasta do lote (nunca é alterada: princípio 2).
        profile: perfil do cliente.
        image_source: porta de leitura de imagens.
        metadata_reader: porta de metadados.
        numbering_reader: porta de leitura da numeração de folhas.
        executor: porta de paralelismo.
        clock: porta de tempo.
        name: nome do lote (padrão: nome da pasta).
        batch_id: identificador; por padrão derivado do conteúdo (determinístico).
        progress: chamado com ``(páginas_prontas, total)``.
        engine_version: versão gravada no resultado.
        fallback_station: identificador da estação usada nas páginas cujo arquivo não
            identifica a digitalizadora (estação padrão do computador ou escolhida ao
            abrir o lote). Ignorado se o perfil não tiver essa estação.
        models_dir: modelos embarcados (orientação). Sem eles, a regra ``orientation`` não
            classifica nenhuma página.
        on_document: chamado a cada processo pronto (menos o último) com o relatório
            parcial dos processos prontos e o identificador do que acabou de ficar pronto
            (liberação por processo, ADR-0018). O retorno é a passada final.
    """
    name = name or root.name
    candidates = sorted(p for p in root.rglob("*") if p.is_file())
    file_meta: dict[str, FileMetadata] = {}
    page_counts: dict[str, int | str] = {}
    from qa_engine.adapters.images import SUPPORTED_SUFFIXES
    from qa_engine.application.layout import RESERVED

    for path in candidates:
        rel = path.relative_to(root).as_posix()
        if path.name in RESERVED or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        file_meta[rel] = metadata_reader.read(path)
        try:
            page_counts[rel] = image_source.page_count(path)
        except LoadError as exc:
            page_counts[rel] = str(exc)
    batch = batch_id or ids.batch_id(_content_key(file_meta))
    multipage = {rel for rel, n in page_counts.items() if isinstance(n, int) and n > 1}
    layouts: list[DocumentLayout] = discover(root, multipage)
    declared = read_manifest(root)

    # Estação de cada arquivo: pelo equipamento ou pasta; senão, a estação de reserva.
    fallback = profile.station(fallback_station)
    file_station = {
        rel: match_station(profile.stations, dict(meta.tags), rel) or fallback
        for rel, meta in file_meta.items()
    }
    from qa_engine.adapters.numbering import SIDECAR_NAME

    has_sidecar = (root / SIDECAR_NAME).is_file()
    read_images = (
        profile.numbering_enabled
        and profile.numbering_reader.enabled
        and not has_sidecar
        and models_dir is not None
    )
    image_numbering = profile.numbering_reader if read_images else None
    rules_cache: dict[str | None, tuple[tuple[str, Mapping[str, Any]], ...]] = {}

    def rules_for(station_id: str | None) -> tuple[tuple[str, Mapping[str, Any]], ...]:
        """Regras de página ligadas e seus parâmetros para uma estação."""
        if station_id not in rules_cache:
            rules_cache[station_id] = tuple(
                (d.id, profile.params(d.id, station_id))
                for d in PAGE_DETECTORS
                if profile.enabled(d.id, station_id)
            )
        return rules_cache[station_id]

    def station_id_of(rel: str) -> str | None:
        station = file_station.get(rel)
        return station.id if station is not None else None

    plan: list[tuple[str, str, int, int | None]] = []  # doc, rel, page_in_file, error marker
    for layout in layouts:
        for ref in layout.files:
            count = page_counts.get(ref.rel, 1)
            if isinstance(count, str) or count == 0:
                plan.append((layout.name, ref.rel, 0, None))
            else:
                plan.extend((layout.name, ref.rel, i, i) for i in range(count))

    tasks = [
        PageTask(
            root / rel,
            page_in_file,
            rules_for(station_id_of(rel)),
            float(profile.params(duplicate_page.ID, station_id_of(rel))["min_ink_coverage"]),
            models_dir,
            image_numbering,
            profile.numbering_reader if profile.numbering_enabled and models_dir else None,
        )
        for _, rel, page_in_file, ok in plan
        if ok is not None
    ]
    results_iter = executor.map(analyze_page, tasks)
    pages: list[Page] = []
    observations: dict[str, dict[str, Observation]] = {}
    scales: dict[str, float] = {}
    prints: list[duplicate_page.Fingerprint] = []
    load_errors: dict[str, str] = {}
    doc_ids = {layout.name: ids.document_id(batch, layout.name) for layout in layouts}
    doc_pages: dict[str, list[str]] = {layout.name: [] for layout in layouts}
    page_keys: dict[str, str] = {
        f"{rel}#{page_in_file}": ids.page_id(batch, rel, page_in_file)
        for _, rel, page_in_file, _ in plan
    }
    by_page_key = {pid: key for key, pid in page_keys.items()}
    stations: dict[str, str] = {}
    station_ids: dict[str, str | None] = {}
    image_marks: dict[str, tuple[Mark, ...]] = {}
    crops: dict[str, bytes] = {}
    written: dict[str, bool] = {}
    faint: dict[str, bool] = {}

    # Numeração do numbering.json: lida antes, para liberar cada processo já com ela.
    if not profile.numbering_enabled:
        source = "none"
        sidecar_marks: Mapping[str, Sequence[Mark]] = {}
    elif image_numbering is not None:
        source = "image"
        sidecar_marks = {}
    else:
        source = "sidecar" if has_sidecar else "none"
        sidecar_marks = numbering_reader.read(root, list(page_keys))

    def marks_of(pid: str) -> tuple[Mark, ...]:
        key = by_page_key[pid]
        found = image_marks.get(key) if image_numbering is not None else sidecar_marks.get(key)
        return tuple(found or ())

    def assemble(ready: Sequence[str], final: bool) -> BatchAnalysis:
        """Relatório dos processos prontos (parcial) ou do lote inteiro (passada final).

        Na parcial, as regras que comparam com o lote usam a mediana do que já foi
        analisado (com os limites absolutos enquanto houver poucas páginas) e a
        duplicata entre páginas fica para a passada final.
        """
        ready_set = set(ready)
        layouts_ready = [layout for layout in layouts if layout.name in ready_set]
        included = {pid for layout in layouts_ready for pid in doc_pages[layout.name]}
        factory = _FindingFactory(batch, profile)
        for pid, error in load_errors.items():
            if pid in included and profile.enabled(corrupted_file.ID):
                factory.add(
                    corrupted_file.ID,
                    Target(TargetKind.PAGE, pid),
                    corrupted_file.flag_load_error(error),
                )
        current = {pid: obs for pid, obs in observations.items() if pid in included}
        # Folha com numeração (ou qualquer escrito na região) nunca é branca.
        for pid, page_obs in current.items():
            blank_obs = page_obs.get(blank_page.ID)
            if blank_obs is not None:
                has_numbering = written.get(pid, False) or bool(marks_of(pid))
                current[pid] = {
                    **page_obs,
                    blank_page.ID: replace(
                        blank_obs,
                        extra={
                            **blank_obs.extra,
                            "numbering_written": has_numbering,
                            "numbering_faint": faint.get(pid, False) and not has_numbering,
                        },
                    ),
                }

        # Linha de base e avaliação de cada página, com os parâmetros da estação dela;
        # a linha de base de uma regra usa todas as páginas em que a regra está ligada.
        baselines: dict[str, dict[str, Stats]] = {}
        page_flags: list[tuple[str, str, Flag]] = []
        for detector in PAGE_DETECTORS:
            measured = {pid: obs[detector.id] for pid, obs in current.items() if detector.id in obs}
            if not measured:
                continue
            baseline = baseline_of(measured.values())
            baselines[detector.id] = baseline
            for pid, obs in measured.items():
                params = dict(rules_for(station_ids[pid]))[detector.id]
                flag = detector.evaluate(obs, baseline, params)
                if flag is not None:
                    page_flags.append((detector.id, pid, flag))
        reviewed_blank = {pid for rule, pid, _ in page_flags if rule == blank_page.ID}
        for rule, pid, flag in page_flags:
            if pid in reviewed_blank and _low_ink_flag(flag):
                continue  # a quase branca já leva o conferente à página
            factory.add(rule, Target(TargetKind.PAGE, pid), flag, scales[pid])

        duplicate_copies: dict[str, str] = {}
        chosen = [p for p in prints if p.page_id in included]
        if final and chosen:

            def dup_params_of(page_id: str) -> Mapping[str, Any]:
                return profile.params(duplicate_page.ID, station_ids[page_id])

            veto_at = float(profile.params(duplicate_page.ID)["numbering_veto_confidence"])

            def folio_of(page_id: str) -> str | None:
                live = [m for m in marks_of(page_id) if not m.struck and m.top is not None]
                if len(live) != 1 or live[0].top is None or live[0].top.confidence < veto_at:
                    return None
                folio = parse_folio(live[0].top.text)
                return None if folio is None else str(folio)

            doc_of = {pid: name for name, pids in doc_pages.items() for pid in pids}
            pairs = duplicate_page.find_duplicates(
                chosen, profile.params(duplicate_page.ID), dup_params_of, folio_of
            )
            for pair in pairs:
                duplicate_copies[pair.copy] = pair.original
                same_doc = doc_of.get(pair.copy) == doc_of.get(pair.original)
                factory.add(
                    duplicate_page.ID,
                    Target(TargetKind.PAGE, pair.copy),
                    _duplicate_flag(
                        pair, dup_params_of(pair.copy), keep_position=pair.copy_first and same_doc
                    ),
                )

        # Sequência e completude por documento.
        documents: list[Document] = []
        numbering: dict[str, PageNumbering] = {}
        proposed: dict[str, tuple[str, ...]] = {}
        for layout in layouts_ready:
            doc_id = doc_ids[layout.name]
            pids = doc_pages[layout.name]
            documents.append(Document(doc_id, batch, layout.name, tuple(pids)))
            if not profile.numbering_enabled:
                continue
            cands = [PageCandidates(pid, marks_of(pid)) for pid in pids]
            seq, flags = sequence.analyze_document(
                doc_id,
                cands,
                profile.sequence_for(source),
                declared.get(layout.name),
                duplicate_copies,
            )
            numbering.update({p.page_id: p for p in seq.pages})
            if seq.reordered:
                proposed[doc_id] = seq.order
            for item in flags:
                if profile.enabled(item.rule):
                    factory.add(item.rule, item.target, item.flag)

        metadata: dict[str, tuple[MetadataField, ...]] = {}
        for ordinal, layout in enumerate(layouts, start=1):
            if layout.name not in ready_set:
                continue
            doc_id = doc_ids[layout.name]
            files = [(ref.rel, file_meta[ref.rel]) for ref in layout.files]
            metadata[doc_id] = tuple(
                document_metadata(
                    profile=profile,
                    batch_id=batch,
                    batch_name=name,
                    document_name=layout.name,
                    document_ordinal=ordinal,
                    files=files,
                    page_count=len(doc_pages[layout.name]),
                )
            )

        findings = tuple(
            sorted(
                factory.findings,
                key=lambda f: (-f.severity.rank, f.rule, f.target.kind.value, f.target.id),
            )
        )
        ready_files = {ref.rel for layout in layouts_ready for ref in layout.files}
        lossy = sorted(
            rel
            for rel, m in file_meta.items()
            if rel in ready_files and m.tags.get("compression") in LOSSY_COMPRESSIONS
        )
        ready_pages = [p for p in pages if p.id in included]
        ready_stations = {pid: st for pid, st in stations.items() if pid in included}
        summary = summarize(
            batch_id=batch,
            profile=profile,
            documents=documents,
            pages=ready_pages,
            findings=findings,
            stations=ready_stations,
            lossy_files=lossy,
        )
        return BatchAnalysis(
            batch_id=batch,
            name=name,
            profile_id=profile.id,
            analyzed_at=clock.now(),
            root=root,
            documents=tuple(documents),
            pages=tuple(ready_pages),
            findings=findings,
            numbering=numbering,
            proposed_order=proposed,
            metadata=metadata,
            files={rel: m for rel, m in file_meta.items() if rel in ready_files},
            stations=ready_stations,
            summary=summary,
            engine_version=engine_version,
            baselines=baselines,
            marks={pid: marks_of(pid) for pid in included},
            numbering_source=source,
            numbering_crops={pid: png for pid, png in crops.items() if pid in included},
            station_ids={pid: st for pid, st in station_ids.items() if pid in included},
            final=final,
            pending_documents=tuple(
                (doc_ids[layout.name], layout.name)
                for layout in layouts
                if layout.name not in ready_set
            ),
        )

    ready: list[str] = []
    for position, (doc_name, rel, page_in_file, ok) in enumerate(plan):
        meta = file_meta[rel]
        pid = page_keys[f"{rel}#{page_in_file}"]
        doc_id = doc_ids[doc_name]
        station = file_station.get(rel)
        stations[pid] = station.location if station else "não identificada"
        station_ids[pid] = station.id if station else None
        if ok is None:
            reason = page_counts[rel] if isinstance(page_counts[rel], str) else "sem páginas"
            result = PageResult(error=str(reason))
        else:
            result = next(results_iter)
        if progress:
            progress(position + 1, len(plan))
        doc_pages[doc_name].append(pid)
        pages.append(
            Page(
                id=pid,
                document_id=doc_id,
                index=len(doc_pages[doc_name]) - 1,
                source_file=rel,
                page_in_file=page_in_file,
                width_px=result.width_px,
                height_px=result.height_px,
                dpi=result.dpi,
                color_mode=result.color_mode,
                sha256=meta.sha256,
                loaded=result.error is None,
            )
        )
        if result.error is not None:
            load_errors[pid] = result.error
        else:
            observations[pid] = dict(result.observations)
            written[pid] = result.written
            faint[pid] = result.faint
            if image_numbering is not None:
                image_marks[f"{rel}#{page_in_file}"] = result.marks
                if result.numbering_crop:
                    crops[pid] = result.numbering_crop
            scales[pid] = result.scale
            if result.fingerprint is not None and profile.enabled(
                duplicate_page.ID, station_ids[pid]
            ):
                dh, thumb, sharp, eligible, view_png, ink_png, rhash = result.fingerprint
                prints.append(
                    duplicate_page.Fingerprint(
                        pid, dh, thumb, sharp, eligible, view_png, ink_png, rhash
                    )
                )
        last_of_doc = position + 1 == len(plan) or plan[position + 1][0] != doc_name
        if last_of_doc:
            ready.append(doc_name)
            # Processo pronto: o conferente já pode abrir (o último sai na passada final).
            if on_document is not None and position + 1 < len(plan):
                on_document(assemble(ready, final=False), doc_ids[doc_name])

    for layout in layouts:  # documento sem nenhuma página no plano
        if layout.name not in ready:
            ready.append(layout.name)
    return assemble(ready, final=True)


def evaluate_page(
    batch_id: str,
    page_id: str,
    result: PageResult,
    profile: Profile,
    baselines: Mapping[str, Mapping[str, Stats]],
    station_id: str | None = None,
    has_numbering: bool = False,
) -> list[Finding]:
    """Sinalizações de uma página avulsa (folha inserida depois), com a linha de base do lote.

    Args:
        batch_id: lote.
        page_id: identificador da página nova.
        result: medidas da página (:func:`analyze_page`).
        profile: perfil do lote.
        baselines: linha de base de cada regra, gravada na análise do lote.
        station_id: estação da página (ajustes de regra).
        has_numbering: a página tem numeração (folha com número nunca é branca).
    """
    factory = _FindingFactory(batch_id, profile)
    target = Target(TargetKind.PAGE, page_id)
    if result.error is not None:
        if profile.enabled(corrupted_file.ID):
            factory.add(corrupted_file.ID, target, corrupted_file.flag_load_error(result.error))
        return factory.findings
    detectors = {d.id: d for d in PAGE_DETECTORS}
    flags: list[tuple[str, Flag]] = []
    for rule, obs in result.observations.items():
        if not profile.enabled(rule, station_id):
            continue
        if rule == blank_page.ID:
            numbered = has_numbering or result.written
            obs = replace(
                obs,
                extra={
                    **obs.extra,
                    "numbering_written": numbered,
                    "numbering_faint": result.faint and not numbered,
                },
            )
        flag = detectors[rule].evaluate(
            obs, baselines.get(rule, {}), profile.params(rule, station_id)
        )
        if flag is not None:
            flags.append((rule, flag))
    blank = any(rule == blank_page.ID for rule, _ in flags)
    for rule, flag in flags:
        if not (blank and _low_ink_flag(flag)):
            factory.add(rule, target, flag, result.scale)
    return factory.findings


def _low_ink_flag(flag: Flag) -> bool:
    """Sinalização feita só por a página ter pouca tinta (inclinação, desfoque, orientação)."""
    return bool(flag.correction.params.get("low_ink"))


def _duplicate_flag(
    pair: duplicate_page.DuplicatePair, params: Mapping[str, Any], keep_position: bool = False
) -> Flag:
    from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass

    correction_params: dict[str, Any] = {"duplicate_of": pair.original}
    if keep_position:
        # A cópia (claramente pior) vem antes: a página que fica ocupa a posição dela.
        correction_params["keep_position"] = True
        text = "Remover esta via (a menos nítida do par); a outra fica na posição desta."
    else:
        text = "Remover esta cópia (a segunda via do par)."
    return Flag(
        severity=Severity.MEDIUM,
        measure=round(pair.similarity, 4),
        threshold=float(params["min_similarity"]),
        confidence=round(min(1.0, 0.5 + pair.similarity / 2), 4),
        correction=Correction(
            CorrectionClass.AUTOMATIC,
            CorrectionAction.REMOVE_PAGE,
            text + " Duas vias legítimas: aprovar (A).",
            correction_params,
        ),
        message=f"Página quase idêntica a outra do lote (semelhança {pair.similarity:.3f}).",
    )
