"""``TextRegionDetector``: detector DB do PP-OCRv5 em ONNX e plano B sem modelo (OpenCV).

O pós-processamento segue o ``inference.yml`` do modelo (``DBPostProcess``: limiar do
mapa 0,3, caixa 0,6, expansão 1,5), sem dependência extra: a expansão do polígono vira
um alargamento do retângulo mínimo pela distância ``área × razão / perímetro``.
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
from qa_engine.ports import TextBox

MODEL_ID = "text-detector"


@cache
def _config(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text("utf-8"))
    ops: dict[str, Any] = {}
    for op in data["PreProcess"]["transform_ops"]:
        ops.update(op if isinstance(op, dict) else {op: None})
    post = data["PostProcess"]
    return {
        "long": int(ops["DetResizeForTest"]["resize_long"]),
        "mean": np.array(ops["NormalizeImage"]["mean"], np.float32),
        "std": np.array(ops["NormalizeImage"]["std"], np.float32),
        "thresh": float(post["thresh"]),
        "box_thresh": float(post["box_thresh"]),
        "unclip": float(post["unclip_ratio"]),
    }


def _sorted(boxes: list[TextBox]) -> list[TextBox]:
    if not boxes:
        return boxes
    line = max(1, int(np.median([b.h for b in boxes]) * 0.6))
    return sorted(boxes, key=lambda b: (b.y // line, b.x))


class PaddleTextDetector:
    """Detector de texto PP-OCRv5 (versão mobile)."""

    def __init__(self, models_dir: Path, max_long: int | None = None) -> None:
        self.model = OnnxRuntimeModel(model_file(models_dir, MODEL_ID, "inference.onnx"))
        self.config = _config(model_file(models_dir, MODEL_ID, "inference.yml"))
        self.max_long = max_long or self.config["long"]

    def detect(self, gray: NDArray[np.uint8]) -> list[TextBox]:
        """Escritos da imagem, em pixels da imagem recebida."""
        h, w = gray.shape[:2]
        scale = min(1.0, self.max_long / max(h, w))
        nh, nw = (max(32, round(h * scale / 32) * 32), max(32, round(w * scale / 32) * 32))
        rgb = cv2.cvtColor(
            cv2.resize(gray, (nw, nh), interpolation=cv2.INTER_AREA), cv2.COLOR_GRAY2RGB
        )
        x = (rgb.astype(np.float32) / 255.0 - self.config["mean"]) / self.config["std"]
        (out,) = self.model.run(
            {self.model.inputs[0]: x.transpose(2, 0, 1)[None].astype(np.float32)}
        )
        prob = out[0, 0]
        mask = (prob > self.config["thresh"]).astype(np.uint8)
        contours, _ = cv2.findContours(mask, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        sx, sy = w / nw, h / nh
        boxes: list[TextBox] = []
        for contour in contours:
            if cv2.contourArea(contour) < 4:
                continue
            filled = np.zeros_like(mask)
            cv2.drawContours(filled, [contour], -1, 1, -1)
            score = float(prob[filled.astype(bool)].mean())
            if score < self.config["box_thresh"]:
                continue
            (cx, cy), (rw, rh), angle = cv2.minAreaRect(contour)
            area, perimeter = rw * rh, 2 * (rw + rh)
            grow = area * self.config["unclip"] / perimeter if perimeter else 0
            points = cv2.boxPoints(((cx, cy), (rw + 2 * grow, rh + 2 * grow), angle))
            x0, y0 = points.min(axis=0)
            x1, y1 = points.max(axis=0)
            bx, by = max(0, int(x0 * sx)), max(0, int(y0 * sy))
            bw, bh = min(w, int(np.ceil(x1 * sx))) - bx, min(h, int(np.ceil(y1 * sy))) - by
            if bw > 2 and bh > 2:
                boxes.append(TextBox(bx, by, bw, bh, round(score, 4)))
        return _sorted(boxes)


class OpenCvTextDetector:
    """Plano B sem modelo: componentes de tinta agrupados por proximidade."""

    def __init__(self, min_height: int = 12) -> None:
        self.min_height = min_height

    def detect(self, gray: NDArray[np.uint8]) -> list[TextBox]:
        """Grupos de traços escuros, alargados na horizontal para juntar os dígitos."""
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        if float(np.percentile(gray, 90)) - float(gray.min()) < 40:
            return []
        h = gray.shape[0]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(3, h // 40), max(3, h // 60)))
        merged = cv2.dilate(ink, kernel)
        count, _, stats, _ = cv2.connectedComponentsWithStats(merged, connectivity=8)
        boxes = [
            TextBox(int(x), int(y), int(bw), int(bh))
            for x, y, bw, bh, area in stats[1:count]
            if bh >= self.min_height and area >= self.min_height**2 // 2
        ]
        return _sorted(boxes)
