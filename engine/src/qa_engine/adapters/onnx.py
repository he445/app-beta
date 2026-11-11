"""``OnnxRuntimeModel``: um modelo ONNX em CPU, uma sessão e uma thread por processo.

Cada processo de análise carrega o modelo uma vez (na primeira chamada) e o reusa;
uma thread por sessão porque o paralelismo já vem dos processos de análise.
Sem PyTorch: só ONNX Runtime.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

_SESSIONS: dict[Path, Any] = {}
_LOCK = threading.Lock()


def _session(path: Path) -> Any:
    import onnxruntime as ort

    with _LOCK:
        if path not in _SESSIONS:
            options = ort.SessionOptions()
            options.intra_op_num_threads = 1
            options.inter_op_num_threads = 1
            options.log_severity_level = 3  # só erros: o log não recebe avisos do grafo
            options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            _SESSIONS[path] = ort.InferenceSession(
                str(path), sess_options=options, providers=["CPUExecutionProvider"]
            )
        return _SESSIONS[path]


class OnnxRuntimeModel:
    """Modelo ONNX carregado sob demanda e compartilhado no processo."""

    def __init__(self, path: Path) -> None:
        self.path = path.resolve()

    @property
    def inputs(self) -> list[str]:
        """Nomes das entradas do grafo."""
        return [i.name for i in _session(self.path).get_inputs()]

    @property
    def outputs(self) -> list[str]:
        """Nomes das saídas do grafo."""
        return [o.name for o in _session(self.path).get_outputs()]

    def run(self, feeds: Mapping[str, NDArray[Any]]) -> list[NDArray[np.float32]]:
        """Roda o grafo e devolve as saídas na ordem do modelo."""
        result: list[NDArray[np.float32]] = _session(self.path).run(None, dict(feeds))
        return result
