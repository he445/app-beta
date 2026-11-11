"""Checagens da documentação que a CI cobra (ADR-0017).

1. Nenhum arquivo versionado cita documento de planejamento que não está no
   repositório: a documentação descreve o sistema como ele é.
2. Todo link relativo em Markdown aponta para um arquivo que existe.
3. As páginas de ``docs/referencia/`` geradas estão em dia com o contrato.
4. Na raiz só ficam os Markdown que o GitHub e as ferramentas esperam ali.

Uso::

    uv run --project engine python tools/docs/check_docs.py
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
# A sigla é montada aqui para que este arquivo não acuse a si mesmo.
FORBIDDEN = re.compile(r"\b" + "A" + "DD" + r"\b")
# Em SQL a mesma palavra é comando (ALTER TABLE ...), e migração publicada não se edita.
SKIP_FORBIDDEN = re.compile(r"(/migrations/[^/]+\.sql|uv\.lock|package-lock\.json)$")
LINK = re.compile(r"\]\((?!https?://|#|mailto:)([^)#\s]+)")
ROOT_MARKDOWN = {"README.md", "CHANGELOG.md", "CONTRIBUTING.md", "LICENSE.md"}
TEXT_SUFFIXES = {
    ".md", ".py", ".ts", ".tsx", ".js", ".cjs", ".css", ".html", ".json", ".yaml", ".yml",
    ".toml", ".txt", ".spec", ".ps1", ".sql", ".cfg", ".ini", "",
}  # fmt: skip


def tracked_files() -> list[Path]:
    """Arquivos versionados e os novos ainda não ignorados."""
    out = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return [REPO / line for line in out.splitlines() if line and (REPO / line).is_file()]


def forbidden_mentions(files: list[Path]) -> list[str]:
    """Linhas que citam o documento de planejamento."""
    errors = []
    for path in files:
        rel = path.relative_to(REPO).as_posix()
        if path.suffix.lower() not in TEXT_SUFFIXES or SKIP_FORBIDDEN.search(f"/{rel}"):
            continue
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            if FORBIDDEN.search(line):
                errors.append(f"{rel}:{number}: cita documento de planejamento fora do repositório")
    return errors


def broken_links(files: list[Path]) -> list[str]:
    """Links relativos de Markdown que não resolvem."""
    errors = []
    for path in files:
        if path.suffix.lower() != ".md":
            continue
        for target in LINK.findall(path.read_text("utf-8")):
            if not (path.parent / target).exists():
                errors.append(f"{path.relative_to(REPO).as_posix()}: link quebrado → {target}")
    return errors


def stray_markdown(files: list[Path]) -> list[str]:
    """Markdown fora de ``docs/`` (a documentação fica numa pasta só)."""
    errors = []
    for path in files:
        rel = path.relative_to(REPO)
        if path.suffix.lower() != ".md" or rel.parts[0] in {"docs", ".github"}:
            continue
        if len(rel.parts) == 1 and rel.name in ROOT_MARKDOWN:
            continue
        if rel.as_posix() == "engine/README.md":  # exigido pelo pyproject do pacote
            continue
        errors.append(f"{rel.as_posix()}: documentação fora de docs/")
    return errors


def stale_reference() -> list[str]:
    """Referência gerada diferente do que o contrato produz agora."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import gen_reference

    out = REPO / "docs" / "referencia"
    return [
        f"docs/referencia/{name}: desatualizada; rode tools/docs/gen_reference.py"
        for name, text in gen_reference.pages().items()
        if not (out / name).is_file() or (out / name).read_text("utf-8") != text
    ]


def run() -> list[str]:
    """Todas as divergências encontradas (lista vazia = documentação em ordem)."""
    files = tracked_files()
    return [
        *forbidden_mentions(files),
        *broken_links(files),
        *stray_markdown(files),
        *stale_reference(),
    ]


def main() -> int:
    """Linha de comando."""
    errors = run()
    for error in errors:
        print(error)
    print("documentação em ordem" if not errors else f"{len(errors)} problema(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
