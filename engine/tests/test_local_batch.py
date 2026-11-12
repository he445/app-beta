"""Lote local lido no lugar (ADR-0013) e lote corrigido gravado em pasta."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from collections.abc import Iterator
from pathlib import Path, PurePath, PureWindowsPath
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient

from conftest import page_150, save
from qa_engine.adapters.corrected_folder import FolderTiffWriter, folder_name
from qa_engine.adapters.images import INACCESSIBLE, FileImageSource
from qa_engine.adapters.local_folder import (
    LocalFolderSource,
    display_path,
    extended_path,
    is_within,
)
from qa_engine.application.contracts import validate
from qa_engine.application.local_batch import (
    FolderNotFoundError,
    LocalBatchError,
    NotAllowedError,
    compare_snapshot,
    open_local_batch,
    take_snapshot,
    wait_until_stable,
)
from qa_engine.detectors import corrupted_file
from qa_engine.entrypoints.http.app import create_app
from qa_engine.entrypoints.http.settings import Settings
from qa_engine.ports import LoadError

FOLDER = LocalFolderSource()


def sha_tree(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(root.rglob("*"))
        if p.is_file()
    }


# Caminhos ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "extended"),
    [
        (r"C:\Lotes\0412", r"\\?\C:\Lotes\0412"),
        (r"C:\Lotes\..\Lotes\0412\.", r"\\?\C:\Lotes\0412"),
        (r"\\servidor\digitalização\lote 0412", r"\\?\UNC\servidor\digitalização\lote 0412"),
        (r"\\?\C:\já\estendido", r"\\?\C:\já\estendido"),
        ("relativo/pasta", "relativo/pasta"),
    ],
)
def test_extended_path_handles_drive_unc_and_long_paths(raw: str, extended: str) -> None:
    assert extended_path(raw) == extended
    if PureWindowsPath(raw).is_absolute() and not raw.startswith("\\\\?\\"):
        assert display_path(extended) == str(
            PureWindowsPath(extended_path(raw)[4:]).as_posix()
        ).replace("/", "\\") or display_path(extended).startswith("\\\\")


def test_long_path_over_260_characters_is_extended() -> None:
    long = "C:\\" + "\\".join(["pasta com acentuação e espaço"] * 12)
    assert len(long) > 260
    assert extended_path(long).startswith("\\\\?\\C:\\")
    assert display_path(extended_path(long)) == long


@pytest.mark.parametrize(
    ("path", "roots", "inside"),
    [
        (r"\\SERVIDOR\Digitalizacao\lote", (r"\\servidor\digitalizacao",), True),
        (r"\\?\UNC\servidor\digitalizacao\lote", (r"\\servidor\digitalizacao",), True),
        (r"D:/Lotes/0412", (r"d:\lotes",), True),
        (r"D:\LotesAntigos\0412", (r"D:\Lotes",), False),
        (r"E:\outro", (r"D:\Lotes", r"\\srv\x"), False),
        (r"E:\qualquer", (), True),
    ],
)
def test_allowed_roots_on_windows(path: str, roots: tuple[str, ...], inside: bool) -> None:
    assert is_within(path, tuple(PureWindowsPath(r) for r in roots), windows=True) is inside


# Abrir e retrato ----------------------------------------------------------------


@pytest.fixture
def local_batch(tmp_path: Path) -> Path:
    """Lote com acento e espaço no caminho, três páginas e um arquivo de numeração."""
    root = tmp_path / "Digitalização" / "Caixa 0412"
    for i in range(1, 4):
        save(root / "Processo 1" / f"{i:04d}.tif", page_150(500 + i, i))
    marks = {
        f"Processo 1/{i:04d}.tif#0": [{"readings": [{"text": str(i), "confidence": 0.95}]}]
        for i in range(1, 4)
    }
    (root / "numbering.json").write_text(json.dumps({"pages": marks}), "utf-8")
    return root


def test_open_local_batch_checks_the_folder(local_batch: Path, tmp_path: Path) -> None:
    batch = open_local_batch(FOLDER, str(local_batch), (), is_within)
    assert batch.name == "Caixa 0412" and batch.images == 3
    with pytest.raises(NotAllowedError):
        open_local_batch(FOLDER, str(local_batch), (PurePath(tmp_path / "outra"),), is_within)
    assert open_local_batch(FOLDER, str(local_batch), (PurePath(tmp_path),), is_within)
    with pytest.raises(FolderNotFoundError):
        open_local_batch(FOLDER, str(tmp_path / "não existe"), (), is_within)
    with pytest.raises(LocalBatchError, match="não é uma pasta"):
        open_local_batch(FOLDER, str(local_batch / "numbering.json"), (), is_within)
    empty = tmp_path / "vazia"
    empty.mkdir()
    (empty / "leia.txt").write_text("x")
    with pytest.raises(LocalBatchError, match="não tem imagens"):
        open_local_batch(FOLDER, str(empty), (), is_within)


def test_snapshot_detects_new_removed_and_changed_files(local_batch: Path) -> None:
    snapshot = take_snapshot(FOLDER, local_batch)
    assert set(snapshot["files"]) == {
        "numbering.json",
        "Processo 1/0001.tif",
        "Processo 1/0002.tif",
        "Processo 1/0003.tif",
    }
    assert compare_snapshot(FOLDER, local_batch, snapshot) == []

    # Mesmo conteúdo com outra data (cópia da pasta): não é mudança.
    page = local_batch / "Processo 1/0001.tif"
    os.utime(page, ns=(time.time_ns(), time.time_ns() + 10**9))
    assert compare_snapshot(FOLDER, local_batch, snapshot) == []

    data = page.read_bytes()
    page.write_bytes(data[:-1] + bytes([data[-1] ^ 0xFF]))  # mesmo tamanho, outro conteúdo
    (local_batch / "Processo 1/0004.tif").write_bytes(b"novo")
    (local_batch / "Processo 1/0003.tif").unlink()
    assert compare_snapshot(FOLDER, local_batch, snapshot) == [
        "arquivo novo: Processo 1/0004.tif",
        "arquivo removido: Processo 1/0003.tif",
        "arquivo alterado: Processo 1/0001.tif",
    ]


def test_wait_until_stable_restarts_the_clock_on_every_change(local_batch: Path) -> None:
    clock = {"now": 0.0}
    writes = iter([2.0, 5.0])
    next_write = next(writes)

    def sleep(seconds: float) -> None:
        nonlocal next_write
        clock["now"] += seconds
        if next_write is not None and clock["now"] >= next_write:
            (local_batch / f"nova-{next_write}.tif").write_bytes(b"x")
            next_write = next(writes, None)

    wait_until_stable(FOLDER, local_batch, 3.0, sleep=sleep, monotonic=lambda: clock["now"])
    assert clock["now"] == 8.0  # última mudança em 5 s + 3 s parada

    clock["now"] = 0.0

    def busy(seconds: float) -> None:
        clock["now"] += seconds
        (local_batch / f"sempre-{clock['now']}.tif").write_bytes(b"x")

    with pytest.raises(TimeoutError):
        wait_until_stable(
            FOLDER, local_batch, 3.0, sleep=busy, monotonic=lambda: clock["now"], timeout=10
        )


def test_locked_or_unreadable_file_becomes_a_warning_not_a_crash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = save(tmp_path / "0001.tif", page_150(1, 1))

    def locked(*_: Any, **__: Any) -> Any:
        raise PermissionError(13, "O arquivo já está sendo usado por outro processo")

    monkeypatch.setattr("PIL.Image.open", locked)
    with pytest.raises(LoadError) as info:
        FileImageSource().load(path, 0, 150)
    assert str(info.value) == INACCESSIBLE
    flag = corrupted_file.flag_load_error(str(info.value))
    assert flag.correction.action.value == "human_review"
    assert "abrir o lote de novo" in flag.correction.description
    assert corrupted_file.flag_load_error("arquivo vazio (0 byte)").correction.action.value == (
        "regenerate"
    )


# Saída em pasta ---------------------------------------------------------------------


def test_folder_writer_publishes_only_when_complete(tmp_path: Path) -> None:
    from datetime import UTC, datetime

    when = datetime(2026, 11, 11, 14, 30, 5, tzinfo=UTC)
    assert folder_name('Caixa: 04/12 "A"', when) == "Caixa_ 04_12 _A_-corrigido-20261111-143005"
    writer = FolderTiffWriter(tmp_path / "saída", "Caixa 0412", when)
    writer.add_page("Processo 1/0001.tif", page_150(1, 1), 150, False, {})
    assert not writer.target.exists()  # pela metade: só a pasta oculta .part
    writer.abort()
    assert list((tmp_path / "saída").iterdir()) == []

    writer = FolderTiffWriter(tmp_path / "saída", "Caixa 0412", when)
    writer.add_page("Processo 1/0001.tif", page_150(1, 1), 150, False, {})
    writer.add_text("manifest.json", "{}")
    path, sha, size = writer.close()
    assert path.name == "Caixa 0412-corrigido-20261111-143005"
    assert sha == hashlib.sha256(b"{}").hexdigest() and size > 0
    assert sorted(p.name for p in (tmp_path / "saída").iterdir()) == [path.name]
    with pytest.raises(ValueError, match="fora da pasta"):
        FolderTiffWriter(tmp_path / "saída", "x", when).add_text("../fuga.txt", "x")
    again = FolderTiffWriter(tmp_path / "saída", "Caixa 0412", when)
    assert again.target.name.endswith("-2")
    again.abort()


# Rota ---------------------------------------------------------------------------------


def make_client(tmp_path: Path, repo: Path, **overrides: Any) -> TestClient:
    profiles = tmp_path / "profiles"
    profiles.mkdir(exist_ok=True)
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    data["resolution"] = {"min_dpi": 150}
    (profiles / "sos-piloto.yaml").write_text(yaml.safe_dump(data, allow_unicode=True), "utf-8")
    options: dict[str, Any] = {
        "data_dir": tmp_path / "data",
        "profiles_dir": profiles,
        "api_token": None,
        "cors_origins": (),
        "retention_hours": 24,
        "max_upload_mb": 50,
        "workers": 1,
        "mode": "desktop",
        "output_dir": tmp_path / "Saída",
        **overrides,
    }
    return TestClient(create_app(Settings(**options)))


@pytest.fixture
def desktop(tmp_path: Path, repo: Path) -> Iterator[TestClient]:
    with make_client(tmp_path, repo) as c:
        yield c


def wait_analyzed(client: TestClient, batch_id: str) -> dict[str, Any]:
    for _ in range(300):
        status: dict[str, Any] = client.get(f"/batches/{batch_id}").json()
        if status["status"] in {"analyzed", "failed"}:
            return status
        time.sleep(0.1)
    raise AssertionError("análise não terminou")


def test_local_batch_route_only_in_desktop_mode(
    tmp_path: Path, repo: Path, local_batch: Path
) -> None:
    with make_client(tmp_path, repo, mode="cloud") as cloud:
        r = cloud.post("/local-batches", json={"path": str(local_batch)})
        assert r.status_code == 404


def test_local_batch_is_read_in_place_and_exported_to_a_folder(
    desktop: TestClient, local_batch: Path, tmp_path: Path
) -> None:
    before = sha_tree(local_batch)
    r = desktop.post("/local-batches", json={"path": str(local_batch), "station_id": "cg-e3"})
    assert r.status_code == 202, r.text
    validate(r.json(), "batch-status.schema.json")
    assert r.json()["source"] == "local" and r.json()["name"] == "Caixa 0412"
    batch_id = r.json()["id"]
    status = wait_analyzed(desktop, batch_id)
    assert status["status"] == "analyzed", status
    assert "stage" not in status
    report = desktop.get(f"/batches/{batch_id}/report").json()
    assert {p["station_id"] for p in report["pages"]} == {"cg-e3"}  # arquivo i4250
    assert not (tmp_path / "data/batches" / batch_id / "input").exists()  # nada copiado

    saved = desktop.post(
        f"/batches/{batch_id}/corrected-batch",
        json={"reviewer": "maria", "destination": "folder"},
    )
    assert saved.status_code == 201, saved.text
    body = saved.json()
    validate(body, "corrected-batch.schema.json")
    assert body["destination"] == "folder" and body["download"] is None
    out = Path(body["folder"])
    assert out.parent == tmp_path / "Saída" and out.name.startswith("Caixa 0412-corrigido-")
    assert sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()) == [
        "Processo 1/0001.tif",
        "Processo 1/0002.tif",
        "Processo 1/0003.tif",
        "configuracao.json",
        "decisions.csv",
        "findings.csv",
        "hashes.sha256",
        "manifest.csv",
        "manifest.json",
        "metadados/Processo 1.json",
        "report.json",
    ]
    assert body["sha256"] == hashlib.sha256((out / "manifest.json").read_bytes()).hexdigest()
    assert sha_tree(local_batch) == before  # o original nunca muda


def test_export_is_blocked_when_the_original_changes(
    desktop: TestClient, local_batch: Path, tmp_path: Path
) -> None:
    batch_id = desktop.post("/local-batches", json={"path": str(local_batch)}).json()["id"]
    assert wait_analyzed(desktop, batch_id)["status"] == "analyzed"
    (local_batch / "Processo 1/0002.tif").write_bytes(b"trocada")
    r = desktop.post(f"/batches/{batch_id}/corrected-batch", json={"reviewer": "maria"})
    assert r.status_code == 409
    assert r.json()["title"] == "Lote original alterado"
    assert "Processo 1/0002.tif" in r.json()["detail"]
    assert not (tmp_path / "Saída").exists() or not list((tmp_path / "Saída").iterdir())


def test_local_batch_errors(
    desktop: TestClient, tmp_path: Path, local_batch: Path, repo: Path
) -> None:
    assert desktop.post("/local-batches", json={"path": str(tmp_path / "x")}).status_code == 404
    r = desktop.post("/local-batches", json={"path": str(local_batch), "station_id": "nao-existe"})
    assert r.status_code == 422
    with make_client(tmp_path, repo, allowed_roots=(tmp_path / "permitida",)) as limited:
        r = limited.post("/local-batches", json={"path": str(local_batch)})
        assert r.status_code == 403 and "allowed_roots" in r.json()["detail"]


def test_purge_never_deletes_the_original_folder(
    tmp_path: Path, repo: Path, local_batch: Path
) -> None:
    before = sha_tree(local_batch)
    with make_client(tmp_path, repo) as c:
        batch_id = c.post("/local-batches", json={"path": str(local_batch)}).json()["id"]
        assert wait_analyzed(c, batch_id)["status"] == "analyzed"
    with make_client(tmp_path, repo, retention_hours=-1) as c:  # tudo vencido
        assert c.get("/batches").json() == []
    assert sha_tree(local_batch) == before
    assert not (tmp_path / "data/batches" / batch_id).exists()
    shutil.rmtree(local_batch)
