import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from PIL import Image

from conftest import page_150, save
from qa_engine.adapters.images import FileImageSource
from qa_engine.adapters.page_versions import FilePageVersionStore
from qa_engine.adapters.system import FixedClock
from qa_engine.application.contracts import validate
from qa_engine.application.corrections import apply_correction
from qa_engine.application.exports import rework_items, write_exports
from qa_engine.application.profile import Profile
from qa_engine.application.review import finding_from_json
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis
from qa_engine.domain.model import TargetKind
from qa_engine.entrypoints.cli.main import main as cli
from qa_engine.ports import LoadError

CLOCK = FixedClock(datetime(2026, 11, 5, tzinfo=UTC))


def rules_by_file(report: dict) -> dict[str, set[str]]:  # type: ignore[type-arg]
    pages = {p["id"]: p for p in report["pages"]}
    out: dict[str, set[str]] = {}
    for f in report["findings"]:
        if f["target"]["kind"] == "page":
            out.setdefault(pages[f["target"]["id"]]["source_file"], set()).add(f["rule"])
    return out


def test_analysis_end_to_end(small_batch: Path, test_profile: Profile, tmp_path: Path) -> None:
    analysis = run_analysis(small_batch, test_profile, workers=1, clock=CLOCK)
    report = analysis_json(analysis)
    validate(report, "analysis.schema.json")
    flagged = rules_by_file(report)
    assert flagged["CX1/DOC1/0007.tif"] == {"skew"}
    assert "blank_page" in flagged["CX1/DOC1/0008.tif"]
    assert "blur" in flagged["CX1/DOC2/0002.tif"]
    assert "CX1/DOC1/0001.tif" not in flagged
    assert [d.name for d in analysis.documents] == ["CX1/DOC1", "CX1/DOC2"]
    # Sem numeração nem manifesto: completude não verificável, nunca "aprovado" calado.
    assert report["batch"]["summary"]["by_rule"]["completeness_unverifiable"] == 2
    assert report["batch"]["summary"]["verdict"] == "rejected"
    meta = {f["name"]: f for f in report["metadata"][analysis.documents[0].id]}
    assert meta["scan_location"]["value"] == "Unidade Campo Grande, Estação 3"
    assert meta["scan_date"]["source"] == "file_tag"
    assert isinstance(meta["hash_sha256"]["value"], dict)  # documento de vários arquivos
    paths = write_exports(report, tmp_path / "out")
    assert {p.name for p in paths} >= {
        "report.json",
        "findings.csv",
        "metadata.csv",
        "rework_order.csv",
    }
    rework = rework_items(report)
    assert any(i["rule"] == "blur" and i["station"].startswith("Unidade") for i in rework)


def test_analysis_is_deterministic(small_batch: Path, test_profile: Profile) -> None:
    a = analysis_json(run_analysis(small_batch, test_profile, workers=1, clock=CLOCK))
    b = analysis_json(run_analysis(small_batch, test_profile, workers=2, clock=CLOCK))
    assert a == b


def test_original_is_untouched_and_correction_fixes_skew(
    small_batch: Path, test_profile: Profile, tmp_path: Path
) -> None:
    before = {p: p.read_bytes() for p in small_batch.rglob("*.tif")}
    analysis = run_analysis(small_batch, test_profile, workers=1, clock=CLOCK)
    report = analysis_json(analysis)
    skew = next(f for f in report["findings"] if f["rule"] == "skew")
    page = next(p for p in report["pages"] if p["id"] == skew["target"]["id"])
    original = FileImageSource().load_original(small_batch / page["source_file"], 0)
    store = FilePageVersionStore(tmp_path / "corrected")
    record = apply_correction(
        finding=finding_from_json(skew),
        original=original,
        dpi=page["dpi"],
        source_sha256=page["sha256"],
        store=store,
        profile=test_profile,
        baselines=analysis.baselines,
        now=CLOCK.now(),
        reviewer="garantidor1",
    )
    assert record.output is not None
    assert (tmp_path / "corrected" / record.output).is_file()
    assert "skew" not in record.remaining_rules
    log = (tmp_path / "corrected/corrections.jsonl").read_text("utf-8").splitlines()
    event = json.loads(log[0])
    assert event["chain"][0]["action"] == "deskew"
    assert event["reviewer"] == "garantidor1"
    assert {p: p.read_bytes() for p in small_batch.rglob("*.tif")} == before


def test_loaders_pdf_multipage_and_corrupted(tmp_path: Path, test_profile: Profile) -> None:
    root = tmp_path / "lote"
    root.mkdir()
    pages = [Image.fromarray(page_150(i)) for i in range(1, 4)]
    pages[0].save(
        root / "contrato.tif",
        save_all=True,
        append_images=pages[1:],
        compression="tiff_deflate",
        dpi=(150, 150),
    )
    pages[0].convert("RGB").save(
        root / "certidao.pdf", save_all=True, append_images=pages[1:2], resolution=150
    )
    (root / "vazio.png").write_bytes(b"")
    save(root / "solta.tif", page_150(9))
    report = analysis_json(run_analysis(root, test_profile, workers=1, clock=CLOCK))
    docs = {d["name"]: len(d["page_ids"]) for d in report["documents"]}
    assert docs == {"certidao": 2, "contrato": 3, "lote": 2}
    pdf_pages = [p for p in report["pages"] if p["source_file"] == "certidao.pdf"]
    assert all(p["loaded"] and p["dpi"] == pytest.approx(150, abs=1) for p in pdf_pages)
    corrupted = [f for f in report["findings"] if f["rule"] == "corrupted_file"]
    assert len(corrupted) == 1
    assert corrupted[0]["target"]["kind"] == TargetKind.PAGE.value
    assert str(tmp_path) not in corrupted[0]["message"]  # sem caminhos do servidor
    with pytest.raises(LoadError):
        FileImageSource().page_count(root / "vazio.png")


def test_manifest_declared_count(small_batch: Path, test_profile: Profile) -> None:
    (small_batch / "manifest.csv").write_text("document,pages\nCX1/DOC2,4\n", encoding="utf-8")
    report = analysis_json(run_analysis(small_batch, test_profile, workers=1, clock=CLOCK))
    docs = {d["id"]: d["name"] for d in report["documents"]}
    missing = [f for f in report["findings"] if f["rule"] == "missing_page"]
    assert [docs[f["target"]["id"]] for f in missing] == ["CX1/DOC2"]


def test_cli(small_batch: Path, tmp_path: Path, full_profile_path: Path) -> None:
    out = tmp_path / "saida"
    assert (
        cli(
            [
                "analyze",
                str(small_batch),
                "--profile",
                str(full_profile_path),
                "--out",
                str(out),
                "--workers",
                "1",
                "--quiet",
            ]
        )
        == 0
    )
    assert cli(["validate-report", str(out / "report.json")]) == 0
    assert cli(["validate-profile", str(full_profile_path)]) == 0
    assert cli(["rules"]) == 0
