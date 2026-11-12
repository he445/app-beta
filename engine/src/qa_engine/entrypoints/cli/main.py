"""``qa``: os mesmos casos de uso da API, sem interface (ADR-0002).

Exemplos::

    qa analyze ./lote --profile profiles/demo.yaml --out ./saida
    qa analyze ./lote --profile profiles/completo.yaml --out ./saida
    qa rules
    qa validate-profile profiles/demo.yaml
    qa admin token                         # gera o token de administrador desta máquina
    qa feedback export --out coleta.zip    # exemplos do beta para o ajuste fino (só local)
    qa beta report --since 2026-12-01      # métricas do piloto a partir do banco local
    qa backup list --all                   # cópias do banco de todas as máquinas
    qa backup restore --latest             # volta a cópia mais nova (programa fechado)
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


def _backup_places(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    """Banco, pasta raiz das cópias e pasta desta máquina e deste usuário."""
    import getpass
    import platform

    from qa_engine.adapters.database_backup import backup_folder

    data_dir = _data_dir(args)
    root: Path | None = args.backup_dir
    if root is None and not args.data_dir:
        from qa_engine.adapters.paths import AppPaths
        from qa_engine.adapters.settings import LayeredSettings

        root = LayeredSettings.for_desktop(AppPaths.detect()).load().settings.backup_dir
    root = root or data_dir / "backups"
    try:
        user = getpass.getuser()
    except (KeyError, OSError):
        user = "usuário"
    return data_dir / "qa.sqlite3", root, backup_folder(root, platform.node() or "estação", user)


def _backup_list(args: argparse.Namespace) -> int:
    """Lista as cópias desta máquina (ou de todas, com --all)."""
    from qa_engine.adapters.database_backup import all_backups, list_backups

    _, root, mine = _backup_places(args)
    if args.all:
        rows = [(f"{m}/{u}", b) for m, u, b in all_backups(root)]
    else:
        rows = [("", b) for b in list_backups(mine)]
    if not rows:
        print(f"nenhuma cópia em {root if args.all else mine}")
        return 1
    for who, item in rows:
        when = item.taken_at.astimezone().strftime("%d/%m/%Y %H:%M:%S")
        size = item.path.stat().st_size / 1024
        print(f"{when}  {size:9.0f} KB  {who + '  ' if who else ''}{item.path}")
    return 0


def _backup_now(args: argparse.Namespace) -> int:
    """Faz uma cópia agora (também com o programa aberto: a API de backup é consistente)."""
    import sqlite3
    from datetime import UTC, datetime

    from qa_engine.adapters.database_backup import take_backup

    db, _, mine = _backup_places(args)
    if not db.is_file():
        print(f"banco não encontrado em {db}: nada a copiar", file=sys.stderr)
        return 1
    try:
        target = take_backup(db, mine, datetime.now(tz=UTC))
    except (OSError, sqlite3.Error) as exc:
        print(f"a cópia falhou: {exc}", file=sys.stderr)
        return 1
    print(f"cópia gravada em {target}")
    return 0


def _backup_restore(args: argparse.Namespace) -> int:
    """Troca o banco desta conta por uma cópia; o atual é guardado ao lado antes."""
    from datetime import UTC, datetime

    from qa_engine.adapters.database_backup import BackupError, list_backups, restore_backup
    from qa_engine.adapters.instance import InstanceLock
    from qa_engine.adapters.sqlite import SqliteRepository

    db, _, mine = _backup_places(args)
    if args.before_update:
        from qa_engine.adapters.database_backup import update_copies

        copies = update_copies(db)
        if not copies:
            print("nenhuma cópia de antes de atualização que esta versão abra", file=sys.stderr)
            return 1
        chosen = copies[0]
    elif args.file is not None:
        chosen = args.file
    elif args.latest:
        newest = list_backups(mine)
        if not newest:
            print(f"nenhuma cópia em {mine}; use qa backup list --all", file=sys.stderr)
            return 1
        chosen = newest[0].path
    else:
        print(
            "diga qual cópia: o arquivo, --latest ou --before-update (veja qa backup list)",
            file=sys.stderr,
        )
        return 2
    lock = InstanceLock(db.parent)
    if not lock.acquire():
        print("feche o programa antes de restaurar (ele está aberto nesta conta)", file=sys.stderr)
        return 1
    try:
        previous = restore_backup(chosen, db, datetime.now(tz=UTC))
    except BackupError as exc:
        print(f"não restaurado: {exc}", file=sys.stderr)
        return 1
    finally:
        lock.release()
    SqliteRepository(db).close()  # cópia de versão anterior: aplica as migrações que faltam
    print(f"banco restaurado de {chosen}")
    if previous is not None:
        print(f"o banco que existia foi guardado em {previous}")
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

    backup = sub.add_parser("backup", help="cópias do banco local (decisões e auditoria)")
    backup_sub = backup.add_subparsers(dest="backup_command", required=True)
    places = argparse.ArgumentParser(add_help=False)
    places.add_argument("--data-dir", type=Path, help="pasta de dados (padrão: a desta conta)")
    places.add_argument(
        "--backup-dir", type=Path, help="pasta das cópias (padrão: backup_dir da configuração)"
    )
    blist = backup_sub.add_parser("list", parents=[places], help="listar as cópias")
    blist.add_argument("--all", action="store_true", help="de todas as máquinas e usuários")
    blist.set_defaults(func=_backup_list)
    bnow = backup_sub.add_parser("now", parents=[places], help="fazer uma cópia agora")
    bnow.set_defaults(func=_backup_now)
    restore = backup_sub.add_parser(
        "restore", parents=[places], help="restaurar uma cópia (com o programa fechado)"
    )
    restore.add_argument("file", type=Path, nargs="?", help="arquivo da cópia")
    restore.add_argument("--latest", action="store_true", help="a cópia mais nova desta conta")
    restore.add_argument(
        "--before-update",
        action="store_true",
        help="a cópia feita antes da última atualização (voltar de versão)",
    )
    restore.set_defaults(func=_backup_restore)

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
