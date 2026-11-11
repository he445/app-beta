"""Gera as páginas de referência a partir do contrato e do código (ADR-0017).

Ninguém edita ``docs/referencia/api.md``, ``perfis.md``, ``configuracao.md`` nem
``cli.md`` à mão: mude o contrato, o manifesto da regra ou o analisador de
argumentos e rode este script.

Uso::

    uv run --project engine python tools/docs/gen_reference.py          # grava
    uv run --project engine python tools/docs/gen_reference.py --check  # só confere
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "referencia"
HEADER = (
    "<!-- Gerado por tools/docs/gen_reference.py. Não edite: mude a fonte e gere de novo. -->\n"
)
METHODS = ("get", "post", "put", "patch", "delete")


def _cell(text: object) -> str:
    return " ".join(str(text).split()).replace("|", "\\|")


def api_page() -> str:
    """Rotas agrupadas pelas etiquetas do OpenAPI."""
    spec = yaml.safe_load((REPO / "contracts" / "openapi.yaml").read_text("utf-8"))
    lines = [
        HEADER,
        "# Referência da API",
        "",
        f"Contrato **{spec['info']['version']}**. A fonte é `contracts/openapi.yaml`, com os",
        "formatos em `contracts/schemas/` (JSON Schema 2020-12), validados pelo Spectral na CI.",
        "Com o motor no ar, a versão interativa fica em `/docs`.",
        "",
        "Erros seguem o RFC 9457 (`application/problem+json`).",
    ]
    by_tag: dict[str, list[tuple[str, str, dict[str, Any]]]] = {}
    for path, item in spec["paths"].items():
        for method in METHODS:
            if method in item:
                op = item[method]
                by_tag.setdefault(op["tags"][0], []).append((method.upper(), path, op))
    for tag in spec["tags"]:
        operations = by_tag.get(tag["name"], [])
        if not operations:
            continue
        lines += [
            "",
            f"## {tag['description']}",
            "",
            "| Rota | Função | Respostas |",
            "| --- | --- | --- |",
        ]
        for method, path, op in operations:
            codes = ", ".join(sorted(op["responses"]))
            lines.append(f"| `{method} {path}` | {_cell(op['summary'])} | {codes} |")
    return "\n".join(lines) + "\n"


def _type(schema: dict[str, Any]) -> str:
    if "enum" in schema:
        return " ou ".join(f"`{v}`" for v in schema["enum"])
    if "const" in schema:
        return f"`{schema['const']}`"
    if "oneOf" in schema or "anyOf" in schema:
        return " ou ".join(_type(s) for s in schema.get("oneOf") or schema["anyOf"])
    kind = schema.get("type", "objeto")
    if isinstance(kind, list):
        return " ou ".join(_type({**schema, "type": k}) for k in kind)
    if kind == "array":
        return f"lista de {_type(schema.get('items', {}))}"
    names = {
        "string": "texto",
        "number": "número",
        "integer": "inteiro",
        "boolean": "sim/não",
        "object": "objeto",
        "null": "vazio",
    }
    return names.get(str(kind), str(kind))


def _limits(schema: dict[str, Any]) -> str:
    parts = []
    if "minimum" in schema:
        parts.append(f"mín. {schema['minimum']}")
    if "maximum" in schema:
        parts.append(f"máx. {schema['maximum']}")
    if "pattern" in schema:
        parts.append(f"padrão `{schema['pattern']}`")
    return ", ".join(parts)


def _rows(schema: dict[str, Any], prefix: str = "") -> list[str]:
    rows: list[str] = []
    required = set(schema.get("required", []))
    for name, prop in schema.get("properties", {}).items():
        key = f"{prefix}{name}"
        default = prop.get("default")
        shown = "" if default is None else f"`{json.dumps(default, ensure_ascii=False)}`"
        about = " ".join(filter(None, [_cell(prop.get("description", "")), _limits(prop)]))
        mark = "sim" if name in required else ""
        rows.append(f"| `{key}` | {_type(prop)} | {mark} | {shown} | {about} |")
        if prop.get("type") == "object" and "properties" in prop:
            rows += _rows(prop, f"{key}.")
        items = prop.get("items", {})
        if prop.get("type") == "array" and "properties" in items:
            rows += _rows(items, f"{key}[].")
    return rows


def profiles_page() -> str:
    """Campos do perfil e parâmetros de cada regra, com os padrões dos manifestos."""
    from qa_engine.detectors.registry import RULES, manifest

    schema = json.loads((REPO / "contracts/schemas/profile.schema.json").read_text("utf-8"))
    lines = [
        HEADER,
        "# Referência de perfis",
        "",
        "Um perfil é um arquivo YAML em `profiles/`, validado contra",
        "`contracts/schemas/profile.schema.json`. Ele diz quais regras ligam, com quais",
        "limiares, e como a numeração e as estações são tratadas.",
        "",
        "## Campos",
        "",
        "| Campo | Tipo | Obrigatório | Padrão | Descrição |",
        "| --- | --- | --- | --- | --- |",
        *_rows(schema),
        "",
        "## Regras e parâmetros",
        "",
        "Cada regra aceita `enabled`, `severity` e `params` em `detectors.<regra>`. Os padrões",
        "abaixo vêm do `manifest.yaml` de cada regra; o perfil só precisa citar o que muda.",
    ]
    for rule in RULES:
        m = manifest(rule)
        spec = Path(m.spec).relative_to("docs").as_posix()
        lines += [
            "",
            f"### `{rule}`",
            "",
            f"{m.title}. Versão {m.version}, severidade `{m.severity.value}`.",
        ]
        lines.append(f"Especificação: [{Path(m.spec).name}](../{spec}).")
        params = m.raw.get("params") or {}
        if not params:
            lines += ["", "Sem parâmetros."]
            continue
        lines += [
            "",
            "| Parâmetro | Tipo | Padrão | Faixa | Descrição |",
            "| --- | --- | --- | --- | --- |",
        ]
        for name, p in params.items():
            lines.append(
                f"| `{name}` | {_type(p)} | `{json.dumps(p['default'], ensure_ascii=False)}` | "
                f"{_limits(p)} | {_cell(p.get('description', ''))} |"
            )
    return "\n".join(lines) + "\n"


def settings_page() -> str | None:
    """Chaves da configuração deste computador (``settings.schema.json``), se existir."""
    path = REPO / "contracts/schemas/settings.schema.json"
    if not path.is_file():
        return None
    schema = json.loads(path.read_text("utf-8"))
    lines = [
        HEADER,
        "# Referência de configuração",
        "",
        _cell(schema.get("description", "")),
        "",
        "A fonte é `contracts/schemas/settings.schema.json`. Como as camadas se combinam e",
        "onde fica cada arquivo: [Configurar este computador](../guias/configurar-computador.md).",
        "",
        "| Chave | Tipo | Obrigatório | Padrão | Descrição |",
        "| --- | --- | --- | --- | --- |",
        *_rows(schema),
    ]
    return "\n".join(lines) + "\n"


def _help(parser: argparse.ArgumentParser, name: str) -> list[str]:
    lines = ["", f"## `{name}`", "", "```text", parser.format_help().rstrip(), "```"]
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            for sub, child in action.choices.items():
                lines += _help(child, f"{name} {sub}")
    return lines


def cli_page() -> str:
    """Ajuda de cada comando, tirada do próprio analisador de argumentos."""
    import os

    from qa_engine.entrypoints.cli.main import build_parser

    os.environ["COLUMNS"] = "100"
    lines = [
        HEADER,
        "# Referência da linha de comando",
        "",
        "O comando `qa` usa os mesmos casos de uso da API, sem interface. Rode com",
        "`uv run --project engine qa <comando>`.",
        *_help(build_parser(), "qa"),
    ]
    return "\n".join(lines) + "\n"


def pages() -> dict[str, str]:
    """Nome do arquivo → conteúdo gerado."""
    result = {"api.md": api_page(), "perfis.md": profiles_page(), "cli.md": cli_page()}
    settings = settings_page()
    if settings is not None:
        result["configuracao.md"] = settings
    return result


def main(argv: list[str] | None = None) -> int:
    """Grava as páginas ou, com ``--check``, acusa as desatualizadas."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="não grava; falha se houver diferença")
    args = parser.parse_args(argv)
    stale = []
    for name, text in pages().items():
        path = OUT / name
        if path.is_file() and path.read_text("utf-8") == text:
            continue
        stale.append(name)
        if not args.check:
            path.write_text(text, "utf-8")
    if args.check and stale:
        print(f"referência desatualizada: {', '.join(stale)}. Rode tools/docs/gen_reference.py.")
        return 1
    print("referência em dia" if not stale else f"gerado: {', '.join(stale)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
