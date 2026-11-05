"""ADR-0003: a dependência aponta para dentro."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "qa_engine"
ALLOWED = {
    "domain": {"qa_engine.domain"},
    "detectors": {"qa_engine.domain", "qa_engine.detectors", "qa_engine.ports"},
    "ports": {"qa_engine.domain", "qa_engine.ports"},
}
FORBIDDEN_THIRD_PARTY = {"domain": {"numpy", "cv2", "PIL", "fastapi", "sqlite3", "yaml"}}


def imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text("utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


@pytest.mark.parametrize("layer", sorted(ALLOWED))
def test_layer_dependencies(layer: str) -> None:
    for path in (SRC / layer).rglob("*.py"):
        for name in imports(path):
            if name.startswith("qa_engine"):
                assert any(name.startswith(a) for a in ALLOWED[layer]), f"{path}: importa {name}"
            assert name.split(".")[0] not in FORBIDDEN_THIRD_PARTY.get(layer, set()), (
                f"{path}: o domínio não pode depender de {name}"
            )
