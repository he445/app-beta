"""Metadados do Decreto no lote corrigido (T30): tags originais, origem de cada valor, hashes."""

from __future__ import annotations

import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any

import cv2
import pytest
import synth
import yaml
from fastapi.testclient import TestClient
from PIL import Image
from PIL.TiffImagePlugin import ImageFileDirectory_v2

from conftest import A5_150, page_150
from qa_engine.application.contracts import validate
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings

SCAN_DATE = "2026:11:05 10:00:00"
ORIGINAL_TAGS = {
    270: "Processo de aposentadoria — São José",  # acento no original volta intacto
    271: "Kodak",
    272: "i4250",
    305: "Kodak Capture Pro 5",
    306: SCAN_DATE,
    315: "operador 7",
    316: "ESTACAO-3",
    33432: "SOS DOCS",
}


def save_tagged(path: Path, gray: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ifd = ImageFileDirectory_v2()
    for number, value in ORIGINAL_TAGS.items():
        ifd[number] = value.encode("utf-8")  # bytes, como a digitalizadora grava
    Image.fromarray(gray).save(path, compression="tiff_deflate", dpi=(150, 150), tiffinfo=ifd)


@pytest.fixture
def tagged_batch(tmp_path: Path) -> Path:
    """Processo com uma página limpa, uma torta (vai ser endireitada) e um JPEG com EXIF."""
    root = tmp_path / "Caixa 0500"
    proc = root / "CX1" / "PROC1"
    save_tagged(proc / "0001.tif", page_150(901, 1))
    skewed = synth.Page(synth.text_page(random.Random(42), (1748, 2480), 2, 5, 2))
    synth.d_skew(skewed, random.Random(7), angle=2.5)
    save_tagged(proc / "0002.tif", cv2.resize(skewed.gray, A5_150, interpolation=cv2.INTER_AREA))
    exif = Image.Exif()
    exif[271], exif[272], exif[306] = "Kodak", "i4250", SCAN_DATE
    exif[0x8769] = {36867: SCAN_DATE, 42033: "SN-4250-77"}
    Image.fromarray(page_150(903, 3)).save(
        proc / "0003.jpg", quality=95, dpi=(150, 150), exif=exif.tobytes()
    )
    marks = {
        f"CX1/PROC1/{name}#0": [{"readings": [{"text": str(i), "confidence": 0.95}]}]
        for i, name in enumerate(["0001.tif", "0002.tif", "0003.jpg"], start=1)
    }
    (root / "numbering.json").write_text(json.dumps({"pages": marks}), "utf-8")
    return root


def client_for(tmp_path: Path, repo: Path, delivery: dict[str, bool] | None = None) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    data["resolution"] = {"min_dpi": 150}
    if delivery is not None:
        data["delivery_metadata"] = delivery
    (profiles / "sos-piloto.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    settings = Settings(
        data_dir=tmp_path / "data",
        profiles_dir=profiles,
        api_token=None,
        cors_origins=(),
        retention_hours=24,
        max_upload_mb=50,
        workers=1,
        mode="desktop",
        output_dir=tmp_path / "Saída",
    )
    return TestClient(create_app(settings))


def deliver(client: TestClient, folder: Path, title: str | None = None) -> Path:
    batch_id = client.post("/local-batches", json={"path": str(folder)}).json()["id"]
    for _ in range(300):
        if client.get(f"/batches/{batch_id}").json()["status"] in {"analyzed", "failed"}:
            break
        time.sleep(0.1)
    report = client.get(f"/batches/{batch_id}/report").json()
    skew = next(f for f in report["findings"] if f["rule"] == "skew")
    r = client.post(
        f"/findings/{skew['id']}/decision", json={"action": "correct", "reviewer": "maria"}
    )
    assert r.status_code == 200, r.text
    if title is not None:
        doc_id = report["documents"][0]["id"]
        r = client.put(
            f"/documents/{doc_id}/metadata/title", json={"value": title, "reviewer": "maria"}
        )
        assert r.status_code == 200, r.text
    saved = client.post(
        f"/batches/{batch_id}/corrected-batch",
        json={"reviewer": "maria", "destination": "folder"},
    )
    assert saved.status_code == 201, saved.text
    return Path(saved.json()["folder"])


def tags_of(path: Path) -> dict[int, Any]:
    with Image.open(path) as tif:
        return dict(tif.tag_v2)


def test_original_tags_decree_fields_with_origin_and_hash_of_every_file(
    tmp_path: Path, repo: Path, tagged_batch: Path
) -> None:
    with client_for(tmp_path, repo) as client:
        out = deliver(client, tagged_batch, title="Aposentadoria de Fulana")

    clean, fixed, from_jpeg = (out / "CX1/PROC1" / f"000{i}.tif" for i in (1, 2, 3))

    # Tags técnicas do original preservadas.
    tags = tags_of(clean)
    for number in (270, 271, 272, 315, 316, 33432):
        # Mesmos bytes do original (o Pillow os mostra em latin-1).
        assert tags[number].encode("latin-1") == ORIGINAL_TAGS[number].encode("utf-8"), number
    assert tags[306] == SCAN_DATE  # página sem correção: a data é a da digitalização
    assert tags[305].startswith("Kodak Capture Pro 5; qa-digitalizacao ")
    assert "sem correcao de imagem" in tags[305]  # ASCII, como pede o TIFF
    xmp = tags[700].decode("utf-8") if isinstance(tags[700], bytes) else tags[700]
    assert "<dc:identifier>" in xmp and "Aposentadoria de Fulana" in xmp
    assert "Unidade Campo Grande, Estação 3" in xmp  # local, do perfil

    # Página corrigida: a tag de software diz o que foi feito; a data passa a ser a da
    # correção e a da digitalização vai para o XMP.
    tags = tags_of(fixed)
    assert "corrigida: endireitada 2,5 graus" in tags[305]
    assert tags[306] != SCAN_DATE
    assert tags[316] == "ESTACAO-3"
    fixed_xmp = tags[700].decode("utf-8")
    assert f"<exif:DateTimeOriginal>{SCAN_DATE}</exif:DateTimeOriginal>" in fixed_xmp
    assert "<qa:corrections>" in fixed_xmp and "<xmp:ModifyDate>" in fixed_xmp

    # JPEG de origem: as tags do EXIF viram tags TIFF e a sub-IFD EXIF vai no XMP.
    tags = tags_of(from_jpeg)
    assert tags[271] == "Kodak"
    jpeg_xmp = tags[700].decode("utf-8")
    assert "<exifEX:BodySerialNumber>SN-4250-77</exifEX:BodySerialNumber>" in jpeg_xmp

    # Arquivo de metadados do processo: valor e origem de cada campo do Decreto.
    meta = json.loads((out / "metadados/CX1-PROC1.json").read_text("utf-8"))
    validate(meta, "delivery-metadata.schema.json")
    decree = {f["name"]: f for f in meta["decree"]}
    assert list(decree)[:4] == ["scan_date", "scan_location", "responsible", "identifier"]
    assert (decree["title"]["value"], decree["title"]["source_label"]) == (
        "Aposentadoria de Fulana",
        "informado pelo revisor",
    )
    assert decree["scan_location"]["source_label"] == "do perfil"
    assert decree["scan_date"]["source_label"] == "do arquivo"
    assert decree["hash_sha256"]["source_label"] == "calculado"
    by_file = {f["target_file"]: f for f in meta["files"]}
    assert by_file["CX1/PROC1/0002.tif"]["corrected"] is True
    assert 316 in by_file["CX1/PROC1/0001.tif"]["preserved_tags"]
    assert by_file["CX1/PROC1/0001.tif"]["xmp"] == "decree"
    for rel, item in by_file.items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == item["sha256"]

    # hashes.sha256: todo arquivo entregue, com o hash certo.
    listed = {}
    for line in (out / "hashes.sha256").read_text("utf-8").splitlines():
        sha, rel = line.split("  ", 1)
        listed[rel] = sha
    files = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} - {
        "hashes.sha256"
    }
    assert set(listed) == files
    for rel, sha in listed.items():
        assert hashlib.sha256((out / rel).read_bytes()).hexdigest() == sha


def test_profile_chooses_where_the_decree_fields_go(
    tmp_path: Path, repo: Path, tagged_batch: Path
) -> None:
    with client_for(tmp_path, repo, {"embed_xmp": False, "document_file": False}) as client:
        out = deliver(client, tagged_batch)
    tags = tags_of(out / "CX1/PROC1/0001.tif")
    assert 700 not in tags  # sem XMP
    assert tags[316] == "ESTACAO-3"  # as tags do original vão sempre
    assert not (out / "metadados").exists()
    assert (out / "hashes.sha256").is_file()
