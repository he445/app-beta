"""Coleta do beta: cada confirmação do revisor vira exemplo rotulado, só nesta máquina.

Numeração: recorte da região, número digitado e as leituras do modelo. Orientação:
miniatura da página, ângulo decidido e a previsão do modelo. ``qa feedback export``
junta tudo num pacote para o ajuste fino feito dentro da empresa
(``docs/especificacoes/coleta-do-beta.md``).
"""

from __future__ import annotations

import json
import zipfile
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from qa_engine.ports import FeedbackExample


def expires(at: str, retention_days: int) -> str:
    """Quando o exemplo vence."""
    return (datetime.fromisoformat(at) + timedelta(days=retention_days)).isoformat()


def numbering_example(
    batch_id: str,
    page: Mapping[str, Any],
    typed: str,
    reviewer: str,
    at: str,
    retention_days: int,
    crop_png: bytes | None,
) -> FeedbackExample:
    """Exemplo de numeração: o que o revisor digitou e o que o modelo tinha resolvido.

    Args:
        batch_id: lote da página.
        page: página do relatório **antes** da digitação (``numbering`` do modelo).
        typed: número digitado pelo revisor.
        reviewer: quem digitou.
        at: quando (ISO 8601).
        retention_days: dias até o exemplo vencer.
        crop_png: recorte da região da numeração, se a análise guardou.
    """
    numbering = page.get("numbering") or {}
    model = {
        "value": numbering.get("value"),
        "state": numbering.get("state"),
        "source": numbering.get("source"),
        "marks": list(numbering.get("marks", [])),
    }
    return FeedbackExample(
        kind="numbering",
        batch_id=batch_id,
        page_id=str(page["id"]),
        reviewer=reviewer,
        created_at=at,
        expires_at=expires(at, retention_days),
        label={"text": typed},
        model=model,
        image_png=crop_png,
    )


def model_angle(finding: Mapping[str, Any]) -> int | None:
    """Ângulo que o modelo propôs (``None`` se a sinalização foi criada pelo revisor)."""
    params = finding["correction"].get("params", {})
    if "model_angle_deg" in params:
        return int(params["model_angle_deg"])
    if params.get("manual"):
        return None
    return int(params.get("angle_deg", 0))


def decided_angle(finding: Mapping[str, Any]) -> int | None:
    """Giro que o revisor deixou: o da correção aceita, 0 se aprovou sem girar."""
    decision = finding.get("decision") or {}
    action = decision.get("action")
    if action == "correct":
        return int(finding["correction"].get("params", {}).get("angle_deg", 0))
    if action == "approve":
        return 0
    return None


def orientation_example(
    batch_id: str,
    finding: Mapping[str, Any],
    reviewer: str,
    at: str,
    retention_days: int,
    thumb_png: bytes | None,
) -> FeedbackExample | None:
    """Exemplo de orientação a partir da decisão do revisor (``None`` se não há ângulo)."""
    angle = decided_angle(finding)
    if angle is None:
        return None
    return FeedbackExample(
        kind="orientation",
        batch_id=batch_id,
        page_id=str(finding["target"]["id"]),
        reviewer=reviewer,
        created_at=at,
        expires_at=expires(at, retention_days),
        label={"angle_deg": angle},
        model={"angle_deg": model_angle(finding), "confidence": finding.get("confidence")},
        image_png=thumb_png,
    )


README = """Pacote da coleta do beta (QA de Digitalização)

Exemplos confirmados pelos garantidores, para o ajuste fino dos modelos feito dentro
da empresa. Contém recortes e miniaturas de páginas de clientes: trate como os próprios
documentos (LGPD) e não envie para fora da rede da empresa.

numeracao/labels.json   recorte da região da numeração; text = número digitado,
                        model = o que o leitor tinha resolvido (formato do
                        tools/bench_numbering.py)
orientacao/labels.json  miniatura da página; angle_deg = giro decidido pelo garantidor,
                        model_angle_deg = previsão do modelo (null = o modelo não viu)
"""


def export_package(examples: Sequence[Mapping[str, Any]], out: Path) -> dict[str, int]:
    """Grava o pacote ``.zip`` com imagens e rótulos; devolve quantos de cada tipo."""
    numbering: list[dict[str, Any]] = []
    orientation: list[dict[str, Any]] = []
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("LEIA-ME.txt", README)
        for i, item in enumerate(examples):
            image: Path | None = item.get("image_path")
            folder = "numeracao" if item["kind"] == "numbering" else "orientacao"
            name = f"{i:05d}.png" if image is not None else None
            if image is not None and name is not None:
                package.write(image, f"{folder}/{name}")
            common = {"file": name, "batch_id": item["batch_id"], "created_at": item["created_at"]}
            if item["kind"] == "numbering":
                numbering.append(
                    {
                        **common,
                        "text": item["label"]["text"],
                        "struck": False,
                        "model": item["model"],
                    }
                )
            else:
                orientation.append(
                    {
                        **common,
                        "angle_deg": item["label"]["angle_deg"],
                        "model_angle_deg": item["model"].get("angle_deg"),
                        "confidence": item["model"].get("confidence"),
                    }
                )
        for folder, labels in (("numeracao", numbering), ("orientacao", orientation)):
            package.writestr(
                f"{folder}/labels.json", json.dumps(labels, ensure_ascii=False, indent=1) + "\n"
            )
    return {"numbering": len(numbering), "orientation": len(orientation)}
