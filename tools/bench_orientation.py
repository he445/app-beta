"""Bench da regra ``orientation``: desfechos por página contra um gabarito.

Roda o mesmo caminho da análise do lote (``analyze_page``: raster de análise, ``skips``,
classificador, ``measure`` e ``evaluate`` com os parâmetros do perfil) em cada página de
uma pasta e compara com o gabarito. O gabarito é um CSV com as colunas ``arquivo``
(caminho relativo à pasta) e ``angulo_real`` (giro horário que a página sofreu: 0, 90,
180 ou 270). Mede o que importa para o garantidor: correção automática errada (nunca
pode acontecer) e página girada que passa sem sinalização (erro silencioso).

Uso::

    uv run --project engine python tools/bench_orientation.py paginas gabarito.csv
        --models models --profile profiles/sos-piloto.yaml [--json] [--set PARAM=VALOR]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from qa_engine.ports import OrientationClassifier

OUTCOMES: dict[str, str] = {
    "upright_ok": "Página certa, não sinalizada (correto)",
    "rotated_auto_ok": "Girada, corrigida automaticamente",
    "rotated_review_ok": "Girada, corrigida com sugestão para revisão",
    "rotated_uncertain": "Girada, enviada para revisão como orientação incerta",
    "rotated_silent": "Girada, não sinalizada (erro silencioso)",
    "rotated_auto_wrong": "Girada, ângulo errado, corrigida automaticamente",
    "rotated_review_wrong": "Girada, ângulo errado, enviada para revisão",
    "upright_auto": "Página certa, girada por engano automaticamente",
    "upright_review": "Página certa, girada por engano, enviada para revisão",
    "upright_uncertain": "Página certa, enviada para revisão como orientação incerta",
}
"""Desfechos possíveis, na ordem do relatório."""

ANGLES = (0, 90, 180, 270)


@dataclass(frozen=True, slots=True)
class PageOutcome:
    """Desfecho de uma página."""

    file: str
    true_angle: int
    predicted: int
    """Ângulo detectado pela regra (0 sem sinalização ou na orientação incerta)."""
    review: bool
    uncertain: bool
    confidence: float | None
    outcome: str

    def json(self) -> dict[str, Any]:
        """Uma linha do relatório."""
        return {
            "file": self.file,
            "true_angle": self.true_angle,
            "predicted": self.predicted,
            "review": self.review,
            "uncertain": self.uncertain,
            "confidence": self.confidence,
            "outcome": self.outcome,
        }


def classify_outcome(true_angle: int, predicted: int, review: bool, uncertain: bool) -> str:
    """Desfecho de uma página a partir do giro real e do que a regra fez."""
    if uncertain:
        return "rotated_uncertain" if true_angle else "upright_uncertain"
    if true_angle == 0:
        if predicted == 0:
            return "upright_ok"
        return "upright_review" if review else "upright_auto"
    if predicted == 0:
        return "rotated_silent"
    right = "ok" if predicted == true_angle else "wrong"
    return f"rotated_{'review' if review else 'auto'}_{right}"


def load_labels(path: Path) -> list[tuple[str, int]]:
    """Gabarito: ``(arquivo, angulo_real)``."""
    with path.open(encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    labels = []
    for row in rows:
        angle = int(row["angulo_real"]) % 360
        if angle not in ANGLES:
            raise ValueError(f"{row['arquivo']}: ângulo {angle} fora de 0/90/180/270")
        labels.append((row["arquivo"], angle))
    return labels


def run_page(
    path: Path,
    params: Mapping[str, Any],
    models: Path | None,
    classifier: OrientationClassifier | None = None,
) -> tuple[int, bool, bool, float | None]:
    """Roda a regra numa página: ``(ângulo detectado, revisão, incerta, confiança)``."""
    from qa_engine.application.analyze import PageTask, analyze_page
    from qa_engine.detectors import orientation

    task = PageTask(path, 0, ((orientation.ID, params),), 0.0, models)
    result = analyze_page(task, classifier=classifier)
    if result.error is not None:
        raise RuntimeError(f"{path}: {result.error}")
    flag = orientation.DETECTOR.evaluate(result.observations[orientation.ID], {}, params)
    if flag is None:
        return 0, False, False, None
    p = flag.correction.params
    uncertain = bool(p.get("uncertain"))
    predicted = 0 if uncertain else int(p["detected_deg"])  # type: ignore[call-overload]
    return predicted, bool(p.get("review")), uncertain, flag.confidence


def bench(
    folder: Path,
    labels: Sequence[tuple[str, int]],
    params: Mapping[str, Any],
    models: Path | None,
    classifier: OrientationClassifier | None = None,
) -> list[PageOutcome]:
    """Desfecho de cada página do gabarito (``classifier`` substitui o dos modelos)."""
    outcomes = []
    for rel, true_angle in labels:
        predicted, review, uncertain, confidence = run_page(
            folder / rel, params, models, classifier
        )
        outcomes.append(
            PageOutcome(
                rel,
                true_angle,
                predicted,
                review,
                uncertain,
                confidence,
                classify_outcome(true_angle, predicted, review, uncertain),
            )
        )
    return outcomes


def summary(outcomes: Sequence[PageOutcome]) -> dict[str, Any]:
    """Contagem por desfecho, acerto por ângulo real e totais."""
    counts = Counter(o.outcome for o in outcomes)
    per_angle = {}
    for angle in ANGLES:
        group = [o for o in outcomes if o.true_angle == angle]
        per_angle[str(angle)] = {
            "hits": sum(o.predicted == angle and not o.uncertain for o in group),
            "n": len(group),
        }
    upright = sum(1 for o in outcomes if o.true_angle == 0)
    upright_reviews = counts["upright_review"] + counts["upright_uncertain"]
    return {
        "n": len(outcomes),
        "outcomes": {key: counts.get(key, 0) for key in OUTCOMES},
        "per_angle": per_angle,
        "automatic_wrong": counts["rotated_auto_wrong"] + counts["upright_auto"],
        "silent": counts["rotated_silent"],
        "reviews": sum(o.review for o in outcomes),
        "upright_review_ratio": round(upright_reviews / upright, 4) if upright else 0.0,
    }


def table(data: Mapping[str, Any]) -> str:
    """Tabelas em texto, no formato do relatório de testes."""
    lines = ["| Desfecho | Páginas |", "| --- | --- |"]
    lines += [f"| {label} | {data['outcomes'][key]} |" for key, label in OUTCOMES.items()]
    lines += ["", "| Orientação real | Acerto |", "| --- | --- |"]
    for angle, item in data["per_angle"].items():
        rate = item["hits"] / item["n"] if item["n"] else 0.0
        lines.append(f"| {angle}° | {item['hits']}/{item['n']} ({rate:.0%}) |")
    lines += [
        "",
        f"páginas: {data['n']} · automáticas erradas: {data['automatic_wrong']} · "
        f"silenciosas: {data['silent']} · revisões: {data['reviews']} · "
        f"páginas certas para revisão: {data['upright_review_ratio']:.1%}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("pages", type=Path, help="pasta das páginas")
    parser.add_argument("labels", type=Path, help="CSV com arquivo,angulo_real")
    parser.add_argument("--models", type=Path, required=True, help="pasta dos modelos")
    parser.add_argument("--profile", type=Path, help="perfil (padrão: o perfil padrão)")
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="PARAM=VALOR",
        help="sobrescreve um parâmetro da regra (ex.: review_threshold=0.5)",
    )
    parser.add_argument("--pages-json", action="store_true", help="inclui cada página no JSON")
    parser.add_argument("--json", action="store_true", help="saída em JSON")
    args = parser.parse_args(argv)
    from qa_engine.application.profile import default_profile, load_profile
    from qa_engine.detectors import orientation

    profile = load_profile(args.profile) if args.profile else default_profile()
    params: dict[str, Any] = dict(profile.params(orientation.ID))
    for item in args.set:
        key, _, value = item.partition("=")
        params[key] = json.loads(value)
    outcomes = bench(args.pages, load_labels(args.labels), params, args.models)
    data = summary(outcomes)
    if args.json:
        if args.pages_json:
            data["pages"] = [o.json() for o in outcomes]
        print(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        print(table(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
