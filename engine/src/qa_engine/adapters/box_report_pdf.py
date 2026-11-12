"""PDF do relatório por caixa (ReportLab, BSD-3-Clause; ADR-0004).

Página A4 simples, para imprimir ou arquivar: cabeçalho com caixa, conferente e data,
e uma linha por processo com as pendências ou "Nenhuma pendência".
"""

from __future__ import annotations

import io
from collections.abc import Mapping
from datetime import datetime
from html import escape
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from qa_engine.application.box_report import process_lines

STATE = {"clean": "Sem pendência", "pending": "Com pendência", "resolved": "Pendência resolvida"}


def _when(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%d/%m/%Y %H:%M")
    except ValueError:
        return iso


def render_box_report_pdf(report: Mapping[str, Any]) -> bytes:
    """O PDF do relatório (determinístico para o mesmo conteúdo)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=16 * mm,
        bottomMargin=16 * mm,
        title=f"Relatório da caixa {report['box']}",  # metadado do PDF, não é marcação
        author=str(report["reviewer"]),
        creator="QA de Digitalização",
        invariant=1,
    )
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("cell", parent=styles["BodyText"], fontSize=10, leading=13)
    story: list[Any] = [
        Paragraph(f"Relatório da caixa {escape(str(report['box']))}", styles["Title"]),
        Paragraph(
            f"Conferente: <b>{escape(str(report['reviewer']))}</b> · Concluída em "
            f"{_when(report['concluded_at'])} · Versão {report['version']} · "
            f"{STATE[report['state']]}",
            styles["Normal"],
        ),
        Paragraph(
            f"Lote {escape(str(report['batch_name']))} · "
            f"{report['totals']['processes']} processo(s), "
            f"{report['totals']['pages']} página(s) · Máquina {escape(str(report['machine']))}, "
            f"programa {escape(str(report['program_version']))}",
            styles["Normal"],
        ),
        Spacer(1, 6 * mm),
    ]
    rows: list[list[Any]] = [
        [Paragraph("<b>Processo</b>", cell), Paragraph("<b>Pendências</b>", cell)]
    ]
    for process in report["processes"]:
        rows.append(
            [
                Paragraph(escape(str(process["number"])), cell),
                Paragraph("<br/>".join(escape(line) for line in process_lines(process)), cell),
            ]
        )
    table = Table(rows, colWidths=[45 * mm, None], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eeeeee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    story.append(table)
    doc.build(story)
    return buffer.getvalue()
