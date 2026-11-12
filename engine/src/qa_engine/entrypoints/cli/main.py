"""``qa``: os mesmos casos de uso da API, sem interface (ADR-0002).

Exemplos::

    qa analyze ./lote --profile profiles/demo.yaml --out ./saida
    qa analyze ./lote --profile profiles/completo.yaml --out ./saida
    qa rules
    qa validate-profile profiles/demo.yaml
    qa admin token                         # gera o token de administrador desta máquina
    qa feedback export --out coleta.zip    # exemplos do beta para o ajuste fino (só local)
    qa beta report --since 2026-12-01      # métricas do piloto a partir do banco local
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

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

    analysis = run_analysis(
        args.batch, profile, workers=args.workers, progress=progress, models_dir=args.models
    )
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


def _admin_token(args: argparse.Namespace) -> int:
    """Gera o token, mostra uma vez e grava só o hash no arquivo da máquina."""
    import tomllib

    from qa_engine.adapters.paths import AppPaths
    from qa_engine.adapters.settings import dump_toml
    from qa_engine.application.admin import hash_token, new_token

    path: Path = args.config or AppPaths.detect().machine_config
    try:
        current = tomllib.loads(path.read_text("utf-8")) if path.is_file() else {}
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"não foi possível ler {path}: {exc}", file=sys.stderr)
        return 1
    token = new_token()
    current["admin_token_hash"] = hash_token(token)
    locked = current.pop("locked", None)
    text = dump_toml(current, "# Configuração desta máquina (TI); o hash vem de qa admin token.")
    if locked:
        keys = ", ".join(f'"{k}"' for k in locked.get("keys", []))
        text += f"\n[locked]\nkeys = [{keys}]\n"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, "utf-8")
    except OSError as exc:
        print(
            f"não foi possível gravar {path}: {exc}. Rode como administrador ou use --config.",
            file=sys.stderr,
        )
        return 1
    print("Token de administrador (mostrado só agora; guarde num lugar seguro):")
    print(token)
    print(f"Hash gravado em {path}. Reabra o programa para valer.")
    return 0


def _data_dir(args: argparse.Namespace) -> Path:
    """Pasta de dados: a indicada ou a do programa desktop desta conta."""
    if args.data_dir:
        return Path(args.data_dir)
    from qa_engine.adapters.paths import AppPaths
    from qa_engine.adapters.settings import LayeredSettings

    return LayeredSettings.for_desktop(AppPaths.detect()).load().settings.data_dir


def _open_store(args: argparse.Namespace) -> tuple[Any, Any, Path] | None:
    from qa_engine.adapters.feedback import SqliteFeedbackStore
    from qa_engine.adapters.sqlite import SqliteRepository

    data_dir = _data_dir(args)
    db = data_dir / "qa.sqlite3"
    if not db.is_file():
        print(f"banco não encontrado em {db}: nenhum lote foi aberto nesta conta", file=sys.stderr)
        return None
    repo = SqliteRepository(db)
    return repo, SqliteFeedbackStore(repo, data_dir), data_dir


def _feedback_export(args: argparse.Namespace) -> int:
    """Pacote com os exemplos confirmados pelos garantidores (fica na rede da empresa)."""
    from qa_engine.application.feedback import export_package

    opened = _open_store(args)
    if opened is None:
        return 1
    repo, store, _ = opened
    try:
        examples = store.examples(args.kind, args.since, args.until)
        counts = export_package(examples, args.out)
    finally:
        repo.close()
    print(
        f"{counts['numbering']} exemplo(s) de numeração e {counts['orientation']} de orientação "
        f"em {args.out}. Contém imagens de documentos: não envie para fora da empresa."
    )
    return 0


def _beta_report(args: argparse.Namespace) -> int:
    """Métricas do piloto, calculadas do banco local (nada sai da máquina)."""
    from datetime import UTC, datetime

    from qa_engine.adapters.local_folder import LocalFolderSource
    from qa_engine.application.beta import beta_report, metrics_for, report_text
    from qa_engine.application.local_batch import SNAPSHOT_FILE, compare_snapshot

    opened = _open_store(args)
    if opened is None:
        return 1
    repo, store, data_dir = opened
    folder = LocalFolderSource()
    try:
        metrics = dict(repo.beta_metrics())
        for row in repo.list_batches():

            def changes(row: Any = row) -> list[str] | None:
                snapshot = data_dir / "batches" / row.id / SNAPSHOT_FILE
                if row.source != "local" or not snapshot.is_file() or not row.root.is_dir():
                    return None
                try:
                    return compare_snapshot(
                        folder, row.root, json.loads(snapshot.read_text("utf-8"))
                    )
                except OSError:
                    return None

            current = metrics_for(repo, row.id, changes)
            if current is not None:
                metrics[row.id] = current
        counts = {
            kind: len(store.examples(kind, args.since, args.until))
            for kind in ("numbering", "orientation")
        }
        report = beta_report(
            list(metrics.values()),
            counts,
            args.since,
            args.until,
            datetime.now(tz=UTC).isoformat(timespec="seconds"),
        )
    finally:
        repo.close()
    validate(report, "beta-report.schema.json")
    text = json.dumps(report, ensure_ascii=False, indent=2) if args.json else report_text(report)
    if args.out:
        args.out.write_text(text + "\n", "utf-8")
        print(f"relatório gravado em {args.out}")
    else:
        print(text)
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
    analyze.add_argument("--models", type=Path, help="pasta dos modelos (orientação da página)")
    analyze.add_argument("--quiet", action="store_true")
    analyze.set_defaults(func=_analyze)

    rules = sub.add_parser("rules", help="listar as regras registradas")
    rules.set_defaults(func=_rules)

    vp = sub.add_parser("validate-profile", help="validar um perfil contra o contrato")
    vp.add_argument("profile", type=Path)
    vp.set_defaults(func=_validate_profile)

    admin = sub.add_parser("admin", help="administração desta máquina")
    admin_sub = admin.add_subparsers(dest="admin_command", required=True)
    token = admin_sub.add_parser("token", help="gerar o token de administrador (diagnóstico)")
    token.add_argument("--config", type=Path, help="arquivo da máquina (padrão: o do sistema)")
    token.set_defaults(func=_admin_token)

    feedback = sub.add_parser("feedback", help="coleta do beta (exemplos confirmados)")
    feedback_sub = feedback.add_subparsers(dest="feedback_command", required=True)
    export = feedback_sub.add_parser("export", help="gerar o pacote para o ajuste fino")
    export.add_argument("--out", type=Path, required=True, help="arquivo .zip de saída")
    export.add_argument("--kind", choices=["numbering", "orientation"], help="só um tipo")
    export.add_argument("--since", help="a partir de (ISO 8601, ex.: 2026-12-01)")
    export.add_argument("--until", help="antes de (ISO 8601)")
    export.add_argument("--data-dir", type=Path, help="pasta de dados (padrão: a desta conta)")
    export.set_defaults(func=_feedback_export)

    beta = sub.add_parser("beta", help="acompanhamento do piloto")
    beta_sub = beta.add_subparsers(dest="beta_command", required=True)
    report = beta_sub.add_parser("report", help="métricas do piloto a partir do banco local")
    report.add_argument("--since", help="lotes criados a partir de (ISO 8601)")
    report.add_argument("--until", help="lotes criados antes de (ISO 8601)")
    report.add_argument(
        "--json", action="store_true", help="saída em JSON (beta-report.schema.json)"
    )
    report.add_argument("--out", type=Path, help="gravar num arquivo em vez de mostrar")
    report.add_argument("--data-dir", type=Path, help="pasta de dados (padrão: a desta conta)")
    report.set_defaults(func=_beta_report)

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
