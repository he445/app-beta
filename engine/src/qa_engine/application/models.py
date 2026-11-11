"""Modelos embarcados: conferência do ``models.lock.json`` ao abrir o programa.

Modelo ausente ou alterado impede a análise com uma mensagem clara, em vez de o
programa cair em silêncio para "sem orientação" ou "sem numeração".
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LOCK_NAME = "models.lock.json"


@dataclass(frozen=True, slots=True)
class ModelsStatus:
    """Resultado da conferência dos modelos."""

    checked: bool
    """Falso quando o motor roda sem modelos configurados (``models_dir`` vazio)."""
    problems: tuple[str, ...] = ()
    models: tuple[dict[str, Any], ...] = field(default_factory=tuple)

    @property
    def ok(self) -> bool:
        """Verdadeiro quando não há o que conferir ou tudo conferiu."""
        return not self.problems

    def json(self) -> dict[str, Any]:
        """Formato de ``models`` em ``/health``."""
        return {"checked": self.checked, "ok": self.ok, "problems": list(self.problems)}


def lock_path(models_dir: Path) -> Path:
    """O ``models.lock.json`` fica ao lado da pasta ``models``."""
    return models_dir.parent / LOCK_NAME


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_models(models_dir: Path | None) -> ModelsStatus:
    """Confere tamanho e SHA-256 de cada arquivo listado no lock."""
    if models_dir is None:
        return ModelsStatus(checked=False)
    lock = lock_path(models_dir)
    if not lock.is_file():
        return ModelsStatus(True, (f"lista de modelos ausente: {LOCK_NAME}",))
    data = json.loads(lock.read_text("utf-8"))
    problems: list[str] = []
    for model in data.get("models", []):
        for item in model.get("files", []):
            path = models_dir / item["path"]
            if not path.is_file():
                problems.append(f"modelo ausente: {item['path']}")
            elif path.stat().st_size != item.get("size", path.stat().st_size):
                problems.append(f"modelo alterado (tamanho): {item['path']}")
            elif _sha256(path) != item["sha256"]:
                problems.append(f"modelo alterado (SHA-256): {item['path']}")
    return ModelsStatus(True, tuple(problems), tuple(data.get("models", [])))


def model_file(models_dir: Path, model_id: str, name: str) -> Path:
    """Caminho de um arquivo de um modelo do lock (``name`` é o nome do arquivo)."""
    data = json.loads(lock_path(models_dir).read_text("utf-8"))
    for model in data.get("models", []):
        if model["id"] == model_id:
            for item in model["files"]:
                if Path(item["path"]).name == name:
                    found: Path = models_dir / str(item["path"])
                    return found
    raise KeyError(f"{model_id}/{name} não está em {LOCK_NAME}")
