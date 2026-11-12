"""Métricas do piloto (``qa beta report``), calculadas do banco desta máquina.

Duas etapas: :func:`batch_metrics` conta o que aconteceu num lote (só números, nada de
conteúdo de documento: as contagens sobrevivem à retenção do lote) e
:func:`beta_report` soma as contagens de um período. As definições estão em
``docs/especificacoes/coleta-do-beta.md``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime
from typing import Any, Protocol

from qa_engine.application.feedback import decided_angle, model_angle

REAL = {"correct", "reject", "source_defect"}
"""Decisões que confirmam o alerta do programa (problema de verdade)."""


class BetaSource(Protocol):
    """O que o relatório do beta lê do banco."""

    def get_batch(self, batch_id: str) -> Any:
        """Linha do lote (``id``, ``name``, ``created_at``) ou ``None``."""
        ...

    def get_report(self, batch_id: str) -> dict[str, Any] | None:
        """Relatório atual do lote."""
        ...

    def decision_log(self, batch_id: str) -> list[dict[str, Any]]:
        """Histórico de decisões, na ordem."""
        ...

    def numbering_override_rows(self, batch_id: str) -> list[dict[str, Any]]:
        """Numerações digitadas com o que o modelo tinha resolvido."""
        ...


def metrics_for(
    source: BetaSource,
    batch_id: str,
    original_changes: Callable[[], Sequence[str] | None] = lambda: None,
) -> dict[str, Any] | None:
    """Contagens de um lote do banco (``None`` se ainda não foi analisado)."""
    row = source.get_batch(batch_id)
    report = source.get_report(batch_id) if row is not None else None
    if row is None or report is None:
        return None
    return batch_metrics(
        {"id": row.id, "name": row.name, "created_at": row.created_at},
        report,
        source.decision_log(batch_id),
        source.numbering_override_rows(batch_id),
        original_changes(),
    )


def _seconds(start: str | None, end: str | None) -> float | None:
    if not start or not end:
        return None
    return max(0.0, (datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())


def _ratio(part: int, whole: int) -> float | None:
    return round(part / whole, 4) if whole else None


def batch_metrics(
    batch: Mapping[str, Any],
    report: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    overrides: Sequence[Mapping[str, Any]],
    original_changes: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Contagens de um lote.

    Args:
        batch: ``id``, ``name`` e ``created_at`` do lote.
        report: relatório atual (com as decisões vigentes).
        decisions: histórico de decisões, na ordem.
        overrides: numerações digitadas, com ``model_value`` e ``model_state``.
        original_changes: o que mudou na pasta original desde o retrato (lote local);
            ``None`` quando não dá para conferir.
    """
    summary = report["batch"]["summary"]
    rules: dict[str, dict[str, int]] = {}
    orientation = {
        "model_decided": 0,
        "kept": 0,
        "changed_angle": 0,
        "reverted": 0,
        "auto_reverted": 0,
        "found_by_reviewer": 0,
    }
    for finding in report["findings"]:
        rule = finding["rule"]
        params = finding["correction"].get("params", {})
        reviewer_made = rule == "orientation" and model_angle(finding) is None
        action = (finding.get("decision") or {}).get("action")
        if rule == "orientation":
            final = decided_angle(finding)
            if reviewer_made:
                orientation["found_by_reviewer"] += int(final not in (None, 0))
            elif final is not None:
                predicted = model_angle(finding)
                orientation["model_decided"] += 1
                if final == predicted:
                    orientation["kept"] += 1
                elif final == 0:
                    orientation["reverted"] += 1
                else:
                    orientation["changed_angle"] += 1
                automatic = not params.get("model_review", params.get("review", False))
                orientation["auto_reverted"] += int(automatic and final != predicted)
        if reviewer_made:
            continue  # sinalização criada pelo revisor não é alerta do programa
        counts = rules.setdefault(rule, {"alerts": 0, "real": 0, "false_positive": 0, "pending": 0})
        counts["alerts"] += 1
        if action in REAL:
            counts["real"] += 1
        elif action == "approve":
            counts["false_positive"] += 1
        else:
            counts["pending"] += 1

    with_numbering = [p for p in report["pages"] if "numbering" in p]
    typed = len(overrides)
    agreed = sum(1 for o in overrides if o.get("model_value") == o["value"])
    missed_numbering = sum(
        1
        for o in overrides
        if o.get("model_state") == "read" and o.get("model_value") not in (None, o["value"])
    )
    times = [d["decided_at"] for d in decisions if d.get("decided_at")]
    times += [o["decided_at"] for o in overrides if o.get("decided_at")]
    return {
        "batch_id": batch["id"],
        "name": batch["name"],
        "created_at": batch["created_at"],
        "pages_total": int(summary["pages_total"]),
        "pages_without_review": int(summary["pages_without_review"]),
        "rules": rules,
        "orientation": orientation,
        "numbering": {
            "pages": len(with_numbering),
            "typed": typed,
            "typed_agreed": agreed,
            "missed": missed_numbering,
        },
        "analysis_seconds": _seconds(batch["created_at"], report["batch"].get("analyzed_at")),
        "review_seconds": _seconds(min(times), max(times)) if times else None,
        "originals": {
            "checked": original_changes is not None,
            "changed": len(original_changes or ()),
        },
    }


def beta_report(
    metrics: Sequence[Mapping[str, Any]],
    feedback: Mapping[str, int],
    since: str | None = None,
    until: str | None = None,
    generated_at: str = "",
) -> dict[str, Any]:
    """Soma as contagens dos lotes criados no período (``beta-report.schema.json``)."""
    chosen = [
        m
        for m in metrics
        if (since is None or m["created_at"] >= since)
        and (until is None or m["created_at"] < until)
    ]
    chosen.sort(key=lambda m: m["created_at"])
    pages = sum(m["pages_total"] for m in chosen)
    no_review = sum(m["pages_without_review"] for m in chosen)

    by_rule: dict[str, dict[str, int]] = {}
    for m in chosen:
        for rule, counts in m["rules"].items():
            total = by_rule.setdefault(rule, dict.fromkeys(counts, 0))
            for key, value in counts.items():
                total[key] = total.get(key, 0) + value
    real = sum(c["real"] for c in by_rule.values())
    false_positive = sum(c["false_positive"] for c in by_rule.values())
    orientation = {key: sum(m["orientation"][key] for m in chosen) for key in _ORIENTATION_KEYS}
    numbering = {key: sum(m["numbering"][key] for m in chosen) for key in _NUMBERING_KEYS}
    found_only = orientation["found_by_reviewer"] + numbering["missed"]
    disagreed = numbering["typed"] - numbering["typed_agreed"]
    analysis = [m["analysis_seconds"] for m in chosen if m["analysis_seconds"] is not None]
    review = [m["review_seconds"] for m in chosen if m["review_seconds"] is not None]
    checked = [m for m in chosen if m["originals"]["checked"]]
    return {
        "generated_at": generated_at,
        "period": {"since": since, "until": until},
        "batches": len(chosen),
        "pages": {
            "total": pages,
            "without_review": no_review,
            "without_review_ratio": _ratio(no_review, pages),
        },
        "defects": {
            "program_alerts": real + false_positive,
            "real": real,
            "false_positive": false_positive,
            "precision": _ratio(real, real + false_positive),
            "found_only_by_reviewer": found_only,
            "recall_estimate": _ratio(real, real + found_only),
            "by_rule": dict(sorted(by_rule.items())),
        },
        "orientation": {
            **orientation,
            "kept_ratio": _ratio(orientation["kept"], orientation["model_decided"]),
        },
        "numbering": {
            **numbering,
            "matched": numbering["pages"] - disagreed,
            "matched_ratio": _ratio(numbering["pages"] - disagreed, numbering["pages"]),
            "typed_ratio": _ratio(numbering["typed"], numbering["pages"]),
        },
        "time": {
            "analysis_seconds_mean": round(sum(analysis) / len(analysis), 1) if analysis else None,
            "review_minutes_mean": round(sum(review) / len(review) / 60, 1) if review else None,
            "per_batch": [
                {
                    "batch_id": m["batch_id"],
                    "name": m["name"],
                    "created_at": m["created_at"],
                    "pages": m["pages_total"],
                    "analysis_seconds": m["analysis_seconds"],
                    "review_minutes": (
                        round(m["review_seconds"] / 60, 1)
                        if m["review_seconds"] is not None
                        else None
                    ),
                }
                for m in chosen
            ],
        },
        "originals": {
            "batches_checked": len(checked),
            "batches_changed": sum(1 for m in checked if m["originals"]["changed"]),
            "files_changed": sum(m["originals"]["changed"] for m in checked),
        },
        "feedback": {
            "numbering": int(feedback.get("numbering", 0)),
            "orientation": int(feedback.get("orientation", 0)),
        },
    }


_ORIENTATION_KEYS = (
    "model_decided",
    "kept",
    "changed_angle",
    "reverted",
    "auto_reverted",
    "found_by_reviewer",
)
_NUMBERING_KEYS = ("pages", "typed", "typed_agreed", "missed")


def report_text(report: Mapping[str, Any]) -> str:
    """O relatório do beta em texto, para o terminal."""

    def pct(value: float | None) -> str:
        return "—" if value is None else f"{value:.1%}".replace(".", ",")

    def dash(value: float | None) -> str:
        return "—" if value is None else f"{value}".replace(".", ",")

    d, o, n, p, t = (report[k] for k in ("defects", "orientation", "numbering", "pages", "time"))
    period = report["period"]
    lines = [
        f"Relatório do beta · {report['batches']} lote(s) · "
        f"de {period['since'] or 'o início'} até {period['until'] or 'agora'}",
        "",
        "Defeitos",
        f"  alertas do programa decididos: {d['program_alerts']} "
        f"({d['real']} problema de verdade, {d['false_positive']} falso positivo; "
        f"precisão {pct(d['precision'])})",
        f"  achados só pelo garantidor: {d['found_only_by_reviewer']} "
        f"(cobertura estimada {pct(d['recall_estimate'])})",
        "Orientação",
        f"  rotações do programa decididas: {o['model_decided']} · mantidas {o['kept']} "
        f"({pct(o['kept_ratio'])}) · outro ângulo {o['changed_angle']} · desfeitas {o['reverted']}",
        f"  rotações automáticas desfeitas: {o['auto_reverted']} (meta: zero)",
        f"  páginas giradas que o garantidor achou sozinho: {o['found_by_reviewer']}",
        "Numeração",
        f"  páginas com numeração: {n['pages']} · bateu com o garantidor: {n['matched']} "
        f"({pct(n['matched_ratio'])}) · precisaram de digitação: {n['typed']} "
        f"({pct(n['typed_ratio'])})",
        "Páginas",
        f"  {p['total']} no total · {p['without_review']} sem precisar de revisão "
        f"({pct(p['without_review_ratio'])})",
        "Tempo",
        f"  análise: {dash(t['analysis_seconds_mean'])} s por lote · "
        f"revisão: {dash(t['review_minutes_mean'])} min por lote (compare com o processo atual)",
        "Originais",
        f"  lotes conferidos: {report['originals']['batches_checked']} · "
        f"com alteração: {report['originals']['batches_changed']} (meta: zero)",
        "Coleta",
        f"  exemplos guardados: {report['feedback']['numbering']} de numeração, "
        f"{report['feedback']['orientation']} de orientação",
    ]
    return "\n".join(lines)
