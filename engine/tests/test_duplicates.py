"""Duplicata com alinhamento (duplicate_page 1.1.0, ADR-0026)."""

from __future__ import annotations

from typing import Any

import cv2
import numpy as np
from numpy.typing import NDArray

from conftest import blank_150, page_150
from qa_engine.application.corrected_batch import build_plan
from qa_engine.detectors import duplicate_page
from qa_engine.detectors.features import compute_features
from qa_engine.detectors.registry import params_for

PARAMS = params_for("duplicate_page", None)


def rescan(gray: NDArray[np.uint8], dx: int, dy: int, angle: float, noise: float = 2.0) -> Any:
    """A mesma folha passada de novo no scanner: deslocada, girada e com outro ruído."""
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    m[0, 2] += dx
    m[1, 2] += dy
    moved = cv2.warpAffine(gray, m, (w, h), borderValue=int(np.median(gray)))
    rng = np.random.default_rng(7)
    return np.clip(moved + rng.normal(0, noise, moved.shape), 0, 255).astype(np.uint8)


def fingerprint(pid: str, gray: NDArray[np.uint8], sharpness: float = 1.0) -> Any:
    features = compute_features(gray)
    view, ink = duplicate_page.views(gray, features.ink)
    return duplicate_page.Fingerprint(
        pid,
        duplicate_page.dhash(gray),
        duplicate_page.thumbnail(gray),
        sharpness,
        features.ink_coverage >= float(PARAMS["min_ink_coverage"]),
        view,
        ink,
        duplicate_page.raster_hash(gray) if features.ink_coverage >= 0.003 else None,
    )


def test_rescan_with_shift_and_rotation_is_a_duplicate_and_the_second_goes() -> None:
    original = page_150(21)
    copy = rescan(original, dx=9, dy=-7, angle=1.5)
    prints = [fingerprint("a", original), fingerprint("x", page_150(22)), fingerprint("b", copy)]
    pairs = duplicate_page.find_duplicates(prints, PARAMS)
    assert [(p.copy, p.original, p.copy_first) for p in pairs] == [("b", "a", False)]
    assert pairs[0].similarity >= float(PARAMS["min_similarity"])


def test_clearly_worse_first_occurrence_goes_and_keeps_its_position() -> None:
    original = page_150(23)
    copy = rescan(original, dx=4, dy=3, angle=-1.0)
    pairs = duplicate_page.find_duplicates(
        [fingerprint("a", original, sharpness=0.3), fingerprint("b", copy, sharpness=1.0)],
        PARAMS,
    )
    assert [(p.copy, p.original, p.copy_first) for p in pairs] == [("a", "b", True)]


def test_repeated_form_with_different_filling_is_not_a_duplicate() -> None:
    form = page_150(24)
    filled_a, filled_b = form.copy(), form.copy()
    for i, (a, b) in enumerate(
        [("JOAO DA SILVA", "MARIA SOUZA"), ("1987", "2003"), ("RUA DAS FLORES 12", "AV BRASIL 900")]
    ):
        y = 640 + 60 * i
        cv2.putText(filled_a, a, (90, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 30, 3)
        cv2.putText(filled_b, b, (90, y), cv2.FONT_HERSHEY_SIMPLEX, 1.1, 30, 3)
    pairs = duplicate_page.find_duplicates(
        [fingerprint("a", filled_a), fingerprint("b", filled_b)], PARAMS
    )
    assert pairs == []


def test_exact_copy_is_found_by_the_raster_hash_even_without_the_comparison() -> None:
    """Cópia exata não depende de tinta nem dos limites da comparação alinhada."""
    from dataclasses import replace

    sparse = blank_150(3).copy()
    cv2.putText(sparse, "OFICIO 12", (300, 600), cv2.FONT_HERSHEY_SIMPLEX, 2.2, 40, 4)
    assert 0.003 <= compute_features(sparse).ink_coverage < 0.01
    # Inelegível para a comparação (estação que exige mais tinta): só o hash pode achar.
    a = replace(fingerprint("a", sparse), eligible=False)
    b = replace(fingerprint("b", sparse.copy()), eligible=False)
    pairs = duplicate_page.find_duplicates([a, b], PARAMS)
    assert [(p.copy, p.similarity) for p in pairs] == [("b", 1.0)]


def test_different_folio_numbers_veto_the_pair() -> None:
    original = page_150(25)
    prints = [fingerprint("a", original), fingerprint("b", rescan(original, 3, 2, 0.5))]
    folios = {"a": "7", "b": "8"}
    assert duplicate_page.find_duplicates(prints, PARAMS, folio_of=folios.get) == []
    same = {"a": "7", "b": "7"}
    assert len(duplicate_page.find_duplicates(prints, PARAMS, folio_of=same.get)) == 1


def _report_with_duplicate(keep_position: bool) -> dict[str, Any]:
    pages = [
        {
            "id": pid,
            "source_file": f"DOC/000{i}.tif",
            "page_in_file": 0,
            "sha256": "0",
            "loaded": True,
            "dpi": 300,
        }
        for i, pid in enumerate(["p1", "p2", "p3"], start=1)
    ]
    finding = {
        "id": "f1",
        "target": {"kind": "page", "id": "p1"},
        "rule": "duplicate_page",
        "rule_version": "1.1.0",
        "severity": "medium",
        "measure": 0.99,
        "threshold": 0.95,
        "confidence": 0.99,
        "message": "duplicata",
        "correction": {
            "kind": "automatic",
            "action": "remove_page",
            "description": "",
            "params": {"duplicate_of": "p3", "keep_position": keep_position},
        },
        "decision": {
            "action": "correct",
            "decided_at": "2026-11-19T10:00:00Z",
            "reviewer": "conferente",
        },
    }
    return {
        "batch": {"id": "lote"},
        "pages": pages,
        "documents": [
            {
                "id": "d",
                "name": "DOC",
                "page_ids": ["p1", "p2", "p3"],
                "proposed_order": None,
                "manual_order": None,
            }
        ],
        "findings": [finding],
    }


def test_kept_page_takes_the_position_of_the_removed_first_occurrence() -> None:
    plan = build_plan(_report_with_duplicate(keep_position=True))
    pages = {p["page_id"]: p for p in plan["documents"][0]["pages"]}
    assert pages["p1"]["status"] == "removed"
    assert (pages["p3"]["new_position"], pages["p2"]["new_position"]) == (1, 2)
    assert pages["p3"]["moved"]
    plain = build_plan(_report_with_duplicate(keep_position=False))
    order = {p["page_id"]: p["new_position"] for p in plain["documents"][0]["pages"]}
    assert (order["p2"], order["p3"]) == (1, 2)
