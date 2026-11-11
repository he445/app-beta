"""Arquivo corrompido (``docs/especificacoes/detectors/corrupted_file.md``).

Não analisa pixels: a aplicação chama :func:`flag_load_error` quando a
porta ``ImageSource`` não consegue decodificar um arquivo ou uma página.
"""

from __future__ import annotations

from qa_engine.detectors.base import Flag
from qa_engine.domain.model import Correction, CorrectionAction, CorrectionClass, Severity

ID = "corrupted_file"


INACCESSIBLE_PREFIX = "arquivo inacessível"


def flag_load_error(reason: str) -> Flag:
    """Sinalização crítica para falha de leitura ou de decodificação.

    Arquivo inacessível (bloqueado por outro programa, sem permissão, rede fora) não
    é defeito do arquivo: a correção é tentar de novo, não redigitalizar.

    Args:
        reason: descrição curta da falha (ex.: ``"arquivo vazio"``).
    """
    if reason.startswith(INACCESSIBLE_PREFIX):
        return Flag(
            severity=Severity.CRITICAL,
            measure=1.0,
            threshold=0.0,
            confidence=1.0,
            correction=Correction(
                CorrectionClass.ESCALATE,
                CorrectionAction.HUMAN_REVIEW,
                "Fechar o programa que está usando o arquivo (ou conferir a rede e a "
                "permissão) e abrir o lote de novo.",
            ),
            message=f"Página não verificada: {reason}.",
        )
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
