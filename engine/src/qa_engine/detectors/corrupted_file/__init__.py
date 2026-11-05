"""Arquivo corrompido (``spec/detectors/corrupted_file.md``).

Não analisa pixels: a aplicação chama :func:`flag_load_error` quando a
porta ``ImageSource`` não consegue decodificar um arquivo ou uma página.
"""

from __future__ import annotations

from qa_engine.detectors.base import Flag
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity

ID = "corrupted_file"


def flag_load_error(reason: str) -> Flag:
    """Sinalização crítica para falha de decodificação.

    Args:
        reason: descrição curta da falha (ex.: ``"arquivo vazio"``).
    """
    return Flag(
        severity=Severity.CRITICAL,
        measure=1.0,
        threshold=0.0,
        confidence=1.0,
        correction=Correction(
            CorrectionClass.PHYSICAL,
            CorrectionAction.REGENERATE,
            "Regerar o arquivo no software de captura ou redigitalizar.",
        ),
        message=f"Arquivo ilegível: {reason}.",
    )
