"""Usado pela CI quando o oasdiff encontra quebra: só passa se a versão maior subiu."""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def major(path: str) -> int:
    """Versão maior de ``info.version``."""
    return int(str(yaml.safe_load(Path(path).read_text("utf-8"))["info"]["version"]).split(".")[0])


if __name__ == "__main__":
    base, head = major(sys.argv[1]), major(sys.argv[2])
    if head > base:
        print(f"quebra de contrato com versão maior {base} → {head}: aceita")
        sys.exit(0)
    print(f"quebra de contrato sem versão maior (continua {head}.x): suba info.version")
    sys.exit(1)
