"""Modelos embarcados: conferência do lock e adaptador ONNX Runtime (sem rede nos testes)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from qa_engine.application.models import model_file, verify_models
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings


def write_lock(base: Path, content: bytes = b"modelo") -> Path:
    models = base / "models"
    (models / "m").mkdir(parents=True)
    (models / "m" / "inference.onnx").write_bytes(content)
    lock = {
        "version": 1,
        "models": [
            {
                "id": "m",
                "files": [
                    {
                        "path": "m/inference.onnx",
                        "sha256": hashlib.sha256(b"modelo").hexdigest(),
                        "size": 6,
                    }
                ],
            }
        ],
    }
    (base / "models.lock.json").write_text(json.dumps(lock), "utf-8")
    return models


def test_models_ok_missing_and_altered(tmp_path: Path) -> None:
    assert verify_models(None).ok and not verify_models(None).checked
    models = write_lock(tmp_path / "ok")
    assert verify_models(models).ok
    assert model_file(models, "m", "inference.onnx") == models / "m/inference.onnx"
    with pytest.raises(KeyError):
        model_file(models, "x", "inference.onnx")

    altered = write_lock(tmp_path / "alterado", b"MODELO")
    assert verify_models(altered).problems == ("modelo alterado (SHA-256): m/inference.onnx",)
    missing = write_lock(tmp_path / "ausente")
    (missing / "m/inference.onnx").unlink()
    assert verify_models(missing).problems == ("modelo ausente: m/inference.onnx",)
    assert not verify_models(tmp_path / "sem-lock" / "models").ok


def test_analysis_is_blocked_with_a_clear_message(tmp_path: Path, full_profile_path: Path) -> None:
    models = write_lock(tmp_path, b"MODELO")
    profiles = tmp_path / "profiles"
    profiles.mkdir()
    (profiles / "demo.yaml").write_text(full_profile_path.read_text("utf-8"), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=None,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=5,
        workers=1,
        models_dir=models,
    )
    with TestClient(create_app(settings)) as client:
        health = client.get("/health").json()
        assert health["models"] == {
            "checked": True,
            "ok": False,
            "problems": ["modelo alterado (SHA-256): m/inference.onnx"],
        }
        r = client.post("/batches", files=[("files", ("a.tif", b"x", "image/tiff"))])
        assert r.status_code == 503
        assert "modelo alterado" in r.json()["title"] and "Reinstale" in r.json()["title"]
        assert not list((tmp_path / "data" / "batches").glob("*/input"))  # nada gravado


def test_onnx_runtime_model_runs_on_cpu(repo: Path) -> None:
    """Com os modelos baixados (build), o de orientação roda; sem eles, o teste é pulado."""
    path = repo / "models" / "PP-LCNet_x1_0_doc_ori_onnx" / "inference.onnx"
    if not path.is_file():
        pytest.skip("modelos não baixados (tools/models/fetch.py)")
    from qa_engine.adapters.onnx import OnnxRuntimeModel

    model = OnnxRuntimeModel(path)
    (out,) = model.run({model.inputs[0]: np.zeros((1, 3, 224, 224), np.float32)})
    assert out.shape == (1, 4)
    assert OnnxRuntimeModel(path).run({"x": np.zeros((1, 3, 224, 224), np.float32)})[0].shape == (
        1,
        4,
    )
