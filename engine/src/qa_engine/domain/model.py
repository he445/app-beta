"""Entidades do domínio, espelhando ``contracts/schemas``.

Os nomes seguem o glossário de ``docs/glossary.md``. As unidades são as do
contrato: pixels com origem no canto superior esquerdo, graus com positivo no
sentido horário, resolução em dpi e datas em ISO 8601 UTC.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import datetime
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    """Severidade de uma sinalização (seção 11 do ADD)."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def rank(self) -> int:
        """Ordem numérica: 3 para crítico, 0 para baixo."""
        return _SEVERITY_RANK[self]


_SEVERITY_RANK: dict[Severity, int] = {
    Severity.CRITICAL: 3,
    Severity.HIGH: 2,
    Severity.MEDIUM: 1,
    Severity.LOW: 0,
}


class TargetKind(StrEnum):
    """Nível ao qual a sinalização se refere."""

    PAGE = "page"
    DOCUMENT = "document"
    BATCH = "batch"


class CorrectionClass(StrEnum):
    """Classe da correção proposta (seção 10 do ADD)."""

    AUTOMATIC = "automatic"
    PHYSICAL = "physical"
    ESCALATE = "escalate"


class CorrectionAction(StrEnum):
    """Ações de correção conhecidas pelo contrato."""

    DESKEW = "deskew"
    ROTATE = "rotate"
    MIRROR = "mirror"
    AUTOCROP = "autocrop"
    DESPECKLE = "despeckle"
    AUTO_LEVELS = "auto_levels"
    REMOVE_PAGE = "remove_page"
    REORDER = "reorder"
    SPLIT = "split"
    MERGE = "merge"
    TO_GRAYSCALE = "to_grayscale"
    RESCAN = "rescan"
    RESCAN_BACK = "rescan_back"
    LOCATE_SHEET = "locate_sheet"
    CLEAN_GLASS = "clean_glass"
    REGENERATE = "regenerate"
    HUMAN_REVIEW = "human_review"


class DecisionAction(StrEnum):
    """Decisão do revisor sobre uma sinalização (seção 12, atalhos A/C/R/O)."""

    APPROVE = "approve"
    CORRECT = "correct"
    REJECT = "reject"
    SOURCE_DEFECT = "source_defect"


class DocumentState(StrEnum):
    """Estado de um documento: verde, amarelo ou vermelho."""

    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class Verdict(StrEnum):
    """Veredito do lote."""

    APPROVED = "approved"
    APPROVED_WITH_RESERVATIONS = "approved_with_reservations"
    REJECTED = "rejected"


class ColorMode(StrEnum):
    """Modo de cor do arquivo original."""

    BILEVEL = "bilevel"
    GRAY = "gray"
    RGB = "rgb"


@dataclass(frozen=True, slots=True)
class Region:
    """Retângulo em pixels da imagem original, origem no canto superior esquerdo."""

    x: int
    y: int
    w: int
    h: int

    def scaled(self, factor: float) -> Region:
        """Retorna a região multiplicada por ``factor`` (arredondada)."""
        return Region(
            x=round(self.x * factor),
            y=round(self.y * factor),
            w=max(1, round(self.w * factor)),
            h=max(1, round(self.h * factor)),
        )


@dataclass(frozen=True, slots=True)
class Target:
    """Alvo de uma sinalização."""

    kind: TargetKind
    id: str


@dataclass(frozen=True, slots=True)
class Correction:
    """Correção proposta para uma sinalização. Nunca é aplicada sem decisão."""

    kind: CorrectionClass
    action: CorrectionAction
    description: str
    params: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Decision:
    """Decisão do revisor, registrada com data e hora (princípio 3)."""

    action: DecisionAction
    decided_at: datetime
    reviewer: str
    note: str | None = None


@dataclass(frozen=True, slots=True)
class Finding:
    """Sinalização: o que foi detectado, com medida, limiar e correção (princípio 4)."""

    id: str
    target: Target
    rule: str
    rule_version: str
    severity: Severity
    measure: float
    threshold: float
    confidence: float
    correction: Correction
    message: str
    region: Region | None = None
    decision: Decision | None = None

    @property
    def pending(self) -> bool:
        """Verdadeiro enquanto a sinalização ainda pesa no estado do documento.

        Aprovar (falso positivo), corrigir e marcar defeito de origem resolvem a
        sinalização. Reprovar a mantém pendente até o retrabalho.
        """
        return self.decision is None or self.decision.action is DecisionAction.REJECT

    def decide(self, decision: Decision) -> Finding:
        """Retorna uma cópia com a decisão registrada."""
        return replace(self, decision=decision)


@dataclass(frozen=True, slots=True)
class Page:
    """Página de um documento."""

    id: str
    document_id: str
    index: int
    source_file: str
    page_in_file: int
    width_px: int
    height_px: int
    dpi: float | None
    color_mode: ColorMode | None
    sha256: str
    loaded: bool = True


@dataclass(frozen=True, slots=True)
class Document:
    """Documento: sequência ordenada de páginas."""

    id: str
    batch_id: str
    name: str
    page_ids: tuple[str, ...]
