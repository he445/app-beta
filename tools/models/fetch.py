"""Baixa os modelos listados em ``models.lock.json`` e confere o SHA-256 de cada arquivo.

Só roda no build (CI ou máquina de desenvolvimento): o programa nunca baixa nada em
tempo de execução. Arquivo que não confere é apagado e o comando falha.

Uso::

    uv run --project engine python tools/models/fetch.py --out models
    uv run --project engine python tools/models/fetch.py --out models --lock-new  # gera hashes
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LOCK = REPO / "models.lock.json"
CHUNK = 1 << 20


def sha256_of(path: Path) -> str:
    """SHA-256 do arquivo."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download(url: str, target: Path) -> None:
    """Baixa para um arquivo parcial e renomeia no fim."""
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_name(target.name + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "qa-build"})
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
        while chunk := response.read(CHUNK):
            out.write(chunk)
    partial.replace(target)


def main(argv: list[str] | None = None) -> int:
    """Linha de comando."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=REPO / "models")
    parser.add_argument("--lock", type=Path, default=LOCK)
    parser.add_argument("--lock-new", action="store_true", help="preenche sha256 e size vazios")
    args = parser.parse_args(argv)
    lock = json.loads(args.lock.read_text("utf-8"))
    failures = 0
    for model in lock["models"]:
        for item in model["files"]:
            target = args.out / item["path"]
            if not target.is_file() or (item.get("sha256") and sha256_of(target) != item["sha256"]):
                print(f"baixando {item['path']}", flush=True)
                download(item["url"], target)
            digest = sha256_of(target)
            if args.lock_new and not item.get("sha256"):
                item["sha256"], item["size"] = digest, target.stat().st_size
            elif digest != item["sha256"]:
                print(f"SHA-256 não confere: {item['path']}", file=sys.stderr)
                target.unlink()
                failures += 1
    if args.lock_new:
        args.lock.write_text(json.dumps(lock, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print("modelos conferidos" if not failures else f"{failures} arquivo(s) recusado(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
