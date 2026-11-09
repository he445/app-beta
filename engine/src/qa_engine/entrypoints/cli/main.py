"""``qa``: os mesmos casos de uso da API, sem interface (seção 15 do ADD).

Exemplos::

    qa analyze ./lote --profile profiles/demo.yaml --out ./saida
    qa analyze ./lote --profile profiles/completo.yaml --out ./saida
    qa rules
    qa validate-profile profiles/demo.yaml
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from qa_engine import __version__
from qa_engine.application.contracts import ContractError, validate
from qa_engine.application.exports import write_exports
from qa_engine.application.profile import default_profile, load_profile
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis
from qa_engine.detectors.registry import RULES, manifest


def _analyze(args: argparse.Namespace) -> int:
    profile = load_profile(args.profile) if args.profile else default_profile()
    started = time.perf_counter()

    def progress(done: int, total: int) -> None:
        if not args.quiet and (done == total or done % 20 == 0):
            print(f"\r{done}/{total} páginas", end="", file=sys.stderr, flush=True)

    analysis = run_analysis(args.batch, profile, workers=args.workers, progress=progress)
    elapsed = time.perf_counter() - started
    report = analysis_json(analysis)
    validate(report, "analysis.schema.json")
    paths = write_exports(report, args.out)
    s = analysis.summary
    if not args.quiet:
        print(file=sys.stderr)
        print(
            f"Lote {analysis.name}: {s.verdict.value} | {s.pages_total} páginas em {elapsed:.1f}s "
            f"({s.pages_total / elapsed if elapsed else 0:.1f} p/s) | "
            f"{len(analysis.findings)} sinalizações | "
            f"{s.no_review_ratio:.0%} das páginas dispensam revisão",
        )
        print(f"Saída: {args.out} ({len(paths)} arquivos)")
    return 0


def _rules(_: argparse.Namespace) -> int:
    for rule in RULES:
        m = manifest(rule)
        print(f"{m.id:28} {m.version:8} {m.severity.value:9} {m.title}")
    return 0


def _validate_profile(args: argparse.Namespace) -> int:
    try:
        load_profile(args.profile)
    except (ContractError, ValueError) as exc:
        print(f"perfil inválido: {exc}", file=sys.stderr)
        return 1
    print("perfil válido")
    return 0


def _validate_report(args: argparse.Namespace) -> int:
    try:
        validate(json.loads(args.report.read_text("utf-8")), "analysis.schema.json")
    except ContractError as exc:
        print(f"relatório inválido: {exc}", file=sys.stderr)
        return 1
    print("relatório válido")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Monta o analisador de argumentos."""
    parser = argparse.ArgumentParser(prog="qa", description="QA automático de digitalização")
    parser.add_argument("--version", action="version", version=f"qa-engine {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    analyze = sub.add_parser("analyze", help="analisar um lote local")
    analyze.add_argument("batch", type=Path, help="pasta do lote")
    analyze.add_argument("--profile", type=Path, help="perfil YAML do cliente")
    analyze.add_argument("--out", type=Path, required=True, help="pasta de saída")
    analyze.add_argument("--workers", type=int, default=None, help="processos (1 = em série)")
    analyze.add_argument("--quiet", action="store_true")
    analyze.set_defaults(func=_analyze)

    rules = sub.add_parser("rules", help="listar as regras registradas")
    rules.set_defaults(func=_rules)

    vp = sub.add_parser("validate-profile", help="validar um perfil contra o contrato")
    vp.add_argument("profile", type=Path)
    vp.set_defaults(func=_validate_profile)

    vr = sub.add_parser("validate-report", help="validar um report.json contra o contrato")
    vr.add_argument("report", type=Path)
    vr.set_defaults(func=_validate_report)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Ponto de entrada da linha de comando."""
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
