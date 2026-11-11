"""``OrientationClassifier`` com o PP-LCNet_x1_0_doc_ori em ONNX (ficha em ``docs/modelos``).

O pré-processamento segue o ``inference.yml`` publicado com o modelo: lado menor em
256, recorte central de 224 × 224, RGB normalizado, CHW. Os rótulos ``0``, ``90``,
``180`` e ``270`` são o giro horário que a página sofreu (travado por teste).
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from numpy.typing import NDArray

from qa_engine.adapters.onnx import OnnxRuntimeModel
from qa_engine.application.models import model_file
from qa_engine.ports import OrientationPrediction

MODEL_ID = "doc-orientation"


@cache
def _config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text("utf-8"))
    ops: dict[str, Any] = {}
    for op in data["PreProcess"]["transform_ops"]:
        ops.update(op if isinstance(op, dict) else {op: None})
    return {
        "short": int(ops["ResizeImage"]["resize_short"]),
        "crop": int(ops["CropImage"]["size"]),
        "mean": np.array(ops["NormalizeImage"]["mean"], np.float32),
        "std": np.array(ops["NormalizeImage"]["std"], np.float32),
        "scale": float(ops["NormalizeImage"]["scale"]),
        "labels": [int(x) for x in data["PostProcess"]["Topk"]["label_list"]],
    }


def preprocess(gray: NDArray[np.uint8], config: dict[str, Any]) -> NDArray[np.float32]:
    """Página em cinza → tensor 1 × 3 × 224 × 224 do modelo."""
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    h, w = rgb.shape[:2]
    factor = config["short"] / min(h, w)
    rgb = cv2.resize(
        rgb, (max(1, round(w * factor)), max(1, round(h * factor))), interpolation=cv2.INTER_AREA
    )
    h, w = rgb.shape[:2]
    size = config["crop"]
    y, x = max(0, (h - size) // 2), max(0, (w - size) // 2)
    crop = rgb[y : y + size, x : x + size].astype(np.float32) * config["scale"]
    norm = (crop - config["mean"]) / config["std"]
    return np.ascontiguousarray(norm.transpose(2, 0, 1)[None], dtype=np.float32)


class PaddleOrientationClassifier:
    """Classificador de orientação de documento (quatro classes)."""

    def __init__(self, models_dir: Path) -> None:
        self.model = OnnxRuntimeModel(model_file(models_dir, MODEL_ID, "inference.onnx"))
        self.config = _config(model_file(models_dir, MODEL_ID, "inference.yml"))

    def classify(self, gray: NDArray[np.uint8]) -> OrientationPrediction:
        """Ângulo mais provável e probabilidades."""
        (out,) = self.model.run({self.model.inputs[0]: preprocess(gray, self.config)})
        scores = np.asarray(out[0], np.float64)
        if not np.isclose(scores.sum(), 1.0, atol=1e-3) or scores.min() < 0:
            exp = np.exp(scores - scores.max())
            scores = exp / exp.sum()
        probabilities = {
            label: float(p) for label, p in zip(self.config["labels"], scores, strict=True)
        }
        best = max(probabilities, key=lambda k: probabilities[k])
        return OrientationPrediction(best, probabilities[best], probabilities)
