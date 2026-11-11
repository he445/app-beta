"""Configuração deste computador: valores efetivos, origem de cada um e erros.

Tipos puros. A combinação das camadas fica no adaptador (porta
``SettingsSource``) e a validação contra o contrato em
:mod:`qa_engine.application.settings`.
"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LAYERS = ("default", "machine", "user", "env", "args")
"""Camadas, da mais fraca para a mais forte."""
WORKER_MEMORY_MB = 400
"""Memória estimada de um processo de análise (OpenCV, NumPy e uma página A4 a 300 dpi)."""


@dataclass(frozen=True, slots=True)
class SettingsProblem:
    """Um valor de configuração recusado: qual chave, de onde veio e o que era esperado."""

    key: str
    source: str
    """Arquivo, ``variável QA_*`` ou ``argumento``."""
    expected: str
    value: Any = None

    def __str__(self) -> str:
        """Frase única para tela de erro e log."""
        return f"{self.key} em {self.source}: esperado {self.expected}; veio {self.value!r}"

    def json(self) -> dict[str, Any]:
        """Formato de ``settings-problem`` no contrato."""
        return {
            "key": self.key,
            "source": self.source,
            "expected": self.expected,
            "value": self.value,
        }


class SettingsError(ValueError):
    """Configuração inválida. Nunca é ignorada em silêncio."""

    def __init__(self, problems: Sequence[SettingsProblem]) -> None:
        self.problems = tuple(problems)
        super().__init__("; ".join(str(p) for p in self.problems))


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuração efetiva do motor.

    Attributes:
        data_dir: banco SQLite, miniaturas, cópias corrigidas e log.
        profiles_dir: perfis YAML.
        api_token: token exigido em ``Authorization: Bearer``; vazio desliga a autenticação.
        cors_origins: origens de interface aceitas quando ela é publicada noutro endereço.
        retention_hours: lotes enviados e cópias são apagados depois disso.
        max_upload_mb: limite do envio pelo navegador.
        workers: processos de análise; ``None`` = automático (núcleos − 1, mínimo 1).
        demo_dir: lotes de demonstração prontos.
        ui_dir: interface compilada para servir na mesma origem.
        models_dir: modelos embarcados (``models.lock.json`` ao lado); vazio = sem modelos.
        diagnostics_dir: pasta compartilhada de diagnóstico; vazio = só neste computador.
        admin_token_hash: hash do token de administrador; vazio = administração desligada.
        output_dir: destino do lote corrigido gravado em pasta.
        temp_dir: arquivos temporários de correção.
        allowed_roots: pastas de onde se pode abrir lote; vazio = qualquer uma.
        default_station: estação usada quando o arquivo não identifica a digitalizadora.
        batch_settle_seconds: espera sem mudança no lote antes de analisar.
        max_memory_mb: teto de memória da análise; ``None`` = metade da memória da máquina.
        log_level: detalhe do log.
        mode: como o motor está rodando: ``cloud`` (demonstração), ``desktop`` (programa na
            estação) ou ``server`` (servidor interno). Definido pela entrada, não por arquivo.
        trusted_hosts: valores aceitos no cabeçalho ``Host``; vazio = qualquer um. No desktop,
            só o endereço local do próprio programa (outro site na máquina não chega à API).
    """

    data_dir: Path
    profiles_dir: Path
    api_token: str | None
    cors_origins: tuple[str, ...]
    retention_hours: float
    max_upload_mb: int
    workers: int | None
    demo_dir: Path | None = None
    ui_dir: Path | None = None
    models_dir: Path | None = None
    diagnostics_dir: Path | None = None
    admin_token_hash: str | None = None
    output_dir: Path | None = None
    temp_dir: Path | None = None
    allowed_roots: tuple[Path, ...] = ()
    default_station: str | None = None
    batch_settle_seconds: float = 0.0
    max_memory_mb: int | None = None
    log_level: str = "info"
    mode: str = "cloud"
    trusted_hosts: tuple[str, ...] = ()

    @property
    def output_root(self) -> Path:
        """Pasta do lote corrigido gravado em pasta (padrão: ``saida`` em ``data_dir``)."""
        return self.output_dir or self.data_dir / "saida"

    @property
    def temp_root(self) -> Path:
        """Pasta de temporários (padrão: ``tmp`` em ``data_dir``)."""
        return self.temp_dir or self.data_dir / "tmp"

    def effective_workers(self, cpu_count: int | None = None, memory_mb: int | None = None) -> int:
        """Processos de análise que cabem nos núcleos e no teto de memória.

        Args:
            cpu_count: núcleos da máquina (padrão: ``os.cpu_count()``).
            memory_mb: memória total da máquina, usada quando ``max_memory_mb`` é automático.
        """
        cores = cpu_count or os.cpu_count() or 1
        wanted = self.workers if self.workers is not None else max(1, cores - 1)
        ceiling = self.max_memory_mb
        if ceiling is None and memory_mb:
            ceiling = memory_mb // 2
        if ceiling:
            wanted = min(wanted, max(1, ceiling // WORKER_MEMORY_MB))
        return max(1, wanted)


@dataclass(frozen=True, slots=True)
class ResolvedSettings:
    """Resultado de combinar as camadas."""

    settings: Settings
    values: Mapping[str, Any]
    """Valor efetivo de cada chave, no formato do esquema (caminhos como texto)."""
    origins: Mapping[str, str]
    """De qual camada veio cada valor: ``default``, ``machine``, ``user``, ``env`` ou ``args``."""
    locked: frozenset[str] = frozenset()
    """Chaves travadas pelo arquivo da máquina."""
    files: Mapping[str, str | None] = field(default_factory=dict)
    """Caminho do arquivo da máquina e do arquivo do usuário, quando existem."""

    def json(self) -> dict[str, Any]:
        """Formato de ``settings-view.schema.json`` (o token nunca é devolvido)."""
        values = dict(self.values)
        values["api_token"] = None
        if values.get("admin_token_hash"):
            values["admin_token_hash"] = None  # nunca devolvido: só se diz que existe
        return {
            "values": values,
            "origins": dict(self.origins),
            "locked": sorted(self.locked),
            "files": dict(self.files),
        }
