"""``TextRecognizer``: TrOCR small handwritten e PP-OCRv5 rec, em ONNX, com vocabulário de folha.

As leituras ficam restritas ao que forma um número de folha: dígitos, ``fls``, ponto,
hífen, ``v`` (verso) e letra de intercalação. Cada reconhecedor devolve até três
leituras (busca em feixe), com confiança de 0 a 1. Sem PyTorch: ONNX Runtime e, no
TrOCR, a biblioteca ``tokenizers``.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from numpy.typing import NDArray

from qa_engine.adapters.onnx import OnnxRuntimeModel
from qa_engine.application.models import model_file
from qa_engine.domain.sequencing import parse_folio
from qa_engine.ports import TextReading

ALLOWED = set("0123456789-.v ") | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ") | set("fls")
"""Caracteres que podem aparecer num número de folha."""
BEAM = 3
POOL = 8
"""Hipóteses mantidas no feixe; das que formam número de folha, saem as três melhores."""
MAX_TOKENS = 8


def prefer_folios(texts: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Até três hipóteses, primeiro as que formam número de folha, na ordem de probabilidade."""
    folios = [t for t in texts if parse_folio(t[0]) is not None]
    others = [t for t in texts if parse_folio(t[0]) is None]
    return (folios + others)[:BEAM]


def _softmax(x: NDArray[Any]) -> NDArray[np.float64]:
    z = np.asarray(x, np.float64)
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    result: NDArray[np.float64] = e / e.sum(axis=-1, keepdims=True)
    return result


class TrOcrRecognizer:
    """TrOCR small handwritten (codificador e decodificador quantizados)."""

    name = "trocr-small-handwritten"
    MODEL_ID = "text-recognizer-trocr"

    def __init__(self, models_dir: Path) -> None:
        from tokenizers import Tokenizer

        self.encoder = OnnxRuntimeModel(
            model_file(models_dir, self.MODEL_ID, "encoder_model_quantized.onnx")
        )
        self.decoder = OnnxRuntimeModel(
            model_file(models_dir, self.MODEL_ID, "decoder_model_quantized.onnx")
        )
        tokenizer = Tokenizer.from_file(
            str(model_file(models_dir, self.MODEL_ID, "tokenizer.json"))
        )
        generation = json.loads(
            model_file(models_dir, self.MODEL_ID, "generation_config.json").read_text("utf-8")
        )
        prep = json.loads(
            model_file(models_dir, self.MODEL_ID, "preprocessor_config.json").read_text("utf-8")
        )
        self.start = int(generation["decoder_start_token_id"])
        self.eos = int(generation["eos_token_id"])
        self.size = (int(prep["size"]["width"]), int(prep["size"]["height"]))
        self.mean = np.array(prep["image_mean"], np.float32)
        self.std = np.array(prep["image_std"], np.float32)
        self.tokenizer = tokenizer
        self.allowed = self._allowed_ids(tokenizer)

    def _allowed_ids(self, tokenizer: Any) -> NDArray[np.int64]:
        ids = [self.eos]
        for token_id in tokenizer.get_vocab().values():
            text = tokenizer.decode([token_id])
            if text and text.strip() and all(c in ALLOWED for c in text):
                ids.append(token_id)
        return np.array(sorted(set(ids)), np.int64)

    def _pixels(self, gray: NDArray[np.uint8]) -> NDArray[np.float32]:
        rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
        rgb = cv2.resize(rgb, self.size, interpolation=cv2.INTER_CUBIC).astype(np.float32) / 255.0
        pixels: NDArray[np.float32] = ((rgb - self.mean) / self.std).transpose(2, 0, 1)[None]
        return pixels.astype(np.float32)

    def read(self, gray: NDArray[np.uint8]) -> list[TextReading]:
        """Busca em feixe com três hipóteses no vocabulário de folha."""
        hidden = self.encoder.run({"pixel_values": self._pixels(gray)})[0]
        beams: list[tuple[list[int], float]] = [([self.start], 0.0)]
        done: list[tuple[list[int], float]] = []
        for _ in range(MAX_TOKENS):
            ids = np.array([b[0] for b in beams], np.int64)
            logits = self.decoder.run(
                {"input_ids": ids, "encoder_hidden_states": np.repeat(hidden, len(beams), axis=0)}
            )[0]
            restricted = logits[:, -1, self.allowed]
            logp = np.log(_softmax(restricted) + 1e-12)
            candidates: list[tuple[list[int], float]] = []
            for (seq, score), row in zip(beams, logp, strict=True):
                for j in np.argsort(row)[-POOL:]:
                    candidates.append(([*seq, int(self.allowed[j])], score + float(row[j])))
            candidates.sort(key=lambda c: c[1], reverse=True)
            beams = []
            for seq, score in candidates:
                if seq[-1] == self.eos:
                    done.append((seq, score))
                elif len(beams) < POOL:
                    beams.append((seq, score))
            if len(done) >= POOL or not beams:
                break
        done.extend(beams)
        readings: dict[str, float] = {}
        for seq, score in sorted(done, key=lambda c: c[1], reverse=True):
            text = self.tokenizer.decode([t for t in seq[1:] if t != self.eos]).strip()
            if text and text not in readings:
                readings[text] = math.exp(score)
        chosen = prefer_folios(list(readings.items()))
        return [TextReading(t, round(c, 4)) for t, c in chosen]


@cache
def _dictionary(path: Path) -> list[str]:
    data = yaml.safe_load(path.read_text("utf-8"))
    chars: list[str] = list(data["PostProcess"]["character_dict"])
    return ["<blank>", *chars, " "]


class PaddleRecRecognizer:
    """Reconhecedor PP-OCRv5 (CTC), com decodificação em feixe restrita."""

    name = "ppocrv5-mobile-rec"
    MODEL_ID = "text-recognizer-ppocr"
    HEIGHT = 48

    def __init__(self, models_dir: Path) -> None:
        self.model = OnnxRuntimeModel(model_file(models_dir, self.MODEL_ID, "inference.onnx"))
        self.chars = _dictionary(model_file(models_dir, self.MODEL_ID, "inference.yml"))
        self.allowed = np.array(
            [0] + [i for i, c in enumerate(self.chars) if i and c in ALLOWED and c != " "], np.int64
        )

    def _pixels(self, gray: NDArray[np.uint8]) -> NDArray[np.float32]:
        h, w = gray.shape[:2]
        width = max(self.HEIGHT, min(640, round(w * self.HEIGHT / h)))
        bgr = cv2.cvtColor(
            cv2.resize(gray, (width, self.HEIGHT), interpolation=cv2.INTER_CUBIC),
            cv2.COLOR_GRAY2BGR,
        )
        x: NDArray[np.float32] = (bgr.astype(np.float32) / 255.0 - 0.5) / 0.5
        return x.transpose(2, 0, 1)[None].astype(np.float32)

    def read(self, gray: NDArray[np.uint8]) -> list[TextReading]:
        """Busca em feixe CTC (prefixos) com três hipóteses."""
        (out,) = self.model.run({self.model.inputs[0]: self._pixels(gray)})
        raw = np.asarray(out[0], np.float64)
        if raw.min() >= 0 and np.allclose(raw.sum(axis=-1), 1.0, atol=1e-2):
            # O grafo já entrega probabilidades: renormaliza só entre os caracteres de folha.
            subset = raw[:, self.allowed]
            probs = subset / np.maximum(subset.sum(axis=-1, keepdims=True), 1e-12)
        else:
            probs = _softmax(raw[:, self.allowed])
        # Feixe por prefixo: (prefixo) → (p_termina_em_branco, p_termina_em_letra).
        beams: dict[tuple[int, ...], tuple[float, float]] = {(): (1.0, 0.0)}
        for row in probs:
            top = np.argsort(row)[-6:]
            nxt: dict[tuple[int, ...], tuple[float, float]] = {}
            for prefix, (pb, pnb) in beams.items():
                for k in top:
                    p = float(row[k])
                    if k == 0:
                        b, n = nxt.get(prefix, (0.0, 0.0))
                        nxt[prefix] = (b + (pb + pnb) * p, n)
                        continue
                    extended = (*prefix, int(k))
                    b, n = nxt.get(extended, (0.0, 0.0))
                    if prefix and prefix[-1] == k:
                        nxt[extended] = (b, n + pb * p)
                        sb, sn = nxt.get(prefix, (0.0, 0.0))
                        nxt[prefix] = (sb, sn + pnb * p)
                    else:
                        nxt[extended] = (b, n + (pb + pnb) * p)
            beams = dict(sorted(nxt.items(), key=lambda kv: sum(kv[1]), reverse=True)[:POOL])
        ranked = sorted(beams.items(), key=lambda kv: sum(kv[1]), reverse=True)
        frames = max(1, len(probs))
        # Qualidade: probabilidade média por quadro do melhor caminho; cada hipótese leva a
        # sua parcela entre as três melhores.
        best = sum(ranked[0][1]) if ranked else 0.0
        quality = best ** (1.0 / frames) if best > 0 else 0.0
        texts: list[tuple[str, float]] = []
        for prefix, (pb, pnb) in ranked:
            text = "".join(self.chars[self.allowed[i]] for i in prefix).strip()
            if text and all(t != text for t, _ in texts):
                texts.append((text, pb + pnb))
        texts = prefer_folios(texts)
        total = sum(p for _, p in texts) or 1.0
        readings = [TextReading(t, round(float(quality * p / total), 4)) for t, p in texts]
        return readings


def recognizer_by_name(models_dir: Path, name: str) -> Any:
    """Um reconhecedor pelo nome do perfil (``numbering.recognizer``)."""
    kinds = {TrOcrRecognizer.name: TrOcrRecognizer, PaddleRecRecognizer.name: PaddleRecRecognizer}
    if name not in kinds:
        raise ValueError(f"reconhecedor desconhecido: {name}")
    return kinds[name](models_dir)


def recognizers(models_dir: Path) -> dict[str, Any]:
    """Os reconhecedores disponíveis, pelo nome."""
    return {r.name: r for r in (TrOcrRecognizer(models_dir), PaddleRecRecognizer(models_dir))}
