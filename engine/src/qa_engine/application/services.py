"""Montagem padrão dos adaptadores (raiz de composição)."""

from __future__ import annotations

from pathlib import Path

from qa_engine import __version__
from qa_engine.adapters.images import FileImageSource
from qa_engine.adapters.metadata import PillowMetadataReader
from qa_engine.adapters.numbering import SidecarNumberingReader
from qa_engine.adapters.system import ProcessPoolExecutor, SerialExecutor, SystemClock
from qa_engine.application.analyze import BatchAnalysis, ProgressCallback, analyze_batch
from qa_engine.application.profile import Profile
from qa_engine.ports import Clock


def run_analysis(
    root: Path,
    profile: Profile,
    *,
    workers: int | None = None,
    clock: Clock | None = None,
    name: str | None = None,
    batch_id: str | None = None,
    progress: ProgressCallback | None = None,
) -> BatchAnalysis:
    """Analisa um lote com os adaptadores de referência.

    Args:
        root: pasta do lote.
        profile: perfil do cliente.
        workers: processos; ``1`` executa em série (útil em testes).
        clock: relógio (padrão: do sistema).
        name: nome do lote.
        batch_id: identificador explícito do lote.
        progress: callback de progresso.
    """
    executor = SerialExecutor() if workers == 1 else ProcessPoolExecutor(workers)
    return analyze_batch(
        root,
        profile,
        image_source=FileImageSource(),
        metadata_reader=PillowMetadataReader(),
        numbering_reader=SidecarNumberingReader(),
        executor=executor,
        clock=clock or SystemClock(),
        name=name,
        batch_id=batch_id,
        progress=progress,
        engine_version=__version__,
    )
