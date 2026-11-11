"""Ajustes da digitalizadora por perfil e por estação (ADR-0012)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from conftest import blank_150, page_150, save
from qa_engine.application.contracts import ContractError
from qa_engine.application.profile import Profile, load_profile, profile_from_dict
from qa_engine.application.serialize import analysis_json
from qa_engine.application.services import run_analysis


def pilot(repo: Path, **changes: Any) -> Profile:
    data = yaml.safe_load((repo / "profiles/sos-piloto.yaml").read_text("utf-8"))
    data.update(changes)
    return profile_from_dict(data)


def test_pilot_profile_is_valid(repo: Path) -> None:
    profile = load_profile(repo / "profiles/sos-piloto.yaml")
    assert [s.id for s in profile.stations] == ["cg-e3", "centro-e1"]


def test_param_precedence_manifest_profile_station(repo: Path) -> None:
    """Padrão do manifesto → detectors do perfil → overrides da estação."""
    profile = pilot(repo, detectors={"black_borders": {"params": {"min_fraction": 0.02}}})
    assert profile.params("black_borders") == {
        **profile.params("black_borders"),
        "min_fraction": 0.02,
        "dark_level": 70,
    }
    at_station = profile.params("black_borders", "cg-e3")
    assert (at_station["min_fraction"], at_station["dark_level"]) == (0.02, 60)
    assert profile.params("black_borders", "centro-e1")["dark_level"] == 70
    assert profile.params("black_borders", "nao-existe")["dark_level"] == 70


def test_param_sources_say_where_each_value_came_from(repo: Path) -> None:
    profile = pilot(repo, detectors={"black_borders": {"params": {"min_fraction": 0.02}}})
    sources = profile.param_sources("black_borders", "cg-e3")
    assert sources == {
        "min_fraction": "profile",
        "dark_level": "station",
        "dark_fraction": "manifest",
        **{
            k: v
            for k, v in sources.items()
            if k not in {"min_fraction", "dark_level", "dark_fraction"}
        },
    }
    assert set(sources.values()) == {"manifest", "profile", "station"}
    assert profile.param_sources("low_resolution")["min_dpi"] == "profile"
    assert set(profile.param_sources("blur").values()) == {"manifest"}


def test_station_can_turn_a_rule_off_or_on(repo: Path) -> None:
    profile = pilot(repo)
    assert profile.enabled("duplicate_page") and profile.enabled("duplicate_page", "cg-e3")
    assert not profile.enabled("duplicate_page", "centro-e1")
    off = pilot(repo, detectors={"exposure": {"enabled": False}})
    off_data = dict(off.raw)
    off_data["stations"] = [
        {"id": "a", "location": "A", "overrides": {"exposure": {"enabled": True}}},
        {"id": "b", "location": "B"},
    ]
    custom = profile_from_dict(off_data)
    assert custom.enabled("exposure", "a") and not custom.enabled("exposure", "b")


def test_effective_rules_view(repo: Path) -> None:
    rules = {r["rule"]: r for r in pilot(repo).effective_rules("centro-e1")}
    assert rules["duplicate_page"]["enabled"] is False
    assert rules["duplicate_page"]["enabled_source"] == "station"
    assert rules["exposure"]["enabled_source"] == "profile"
    assert rules["blur"]["enabled_source"] == "manifest"
    dark = next(
        p
        for p in {r["rule"]: r for r in pilot(repo).effective_rules("cg-e3")}["black_borders"][
            "params"
        ]
        if p["name"] == "dark_level"
    )
    assert {k: dark[k] for k in ("name", "value", "source", "default")} == {
        "name": "dark_level",
        "value": 60,
        "source": "station",
        "default": 70,
    }
    assert (dark["type"], dark["minimum"], dark["maximum"]) == ("integer", 0, 255)


@pytest.mark.parametrize(
    ("stations", "message"),
    [
        ([{"id": "a", "location": "A"}, {"id": "a", "location": "B"}], "estação repetida"),
        (
            [{"id": "a", "location": "A", "overrides": {"blur": {"params": {"nao_existe": 1}}}}],
            "parâmetros desconhecidos para blur",
        ),
    ],
)
def test_invalid_stations_are_refused(repo: Path, stations: list[Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        pilot(repo, stations=stations)


def test_unknown_rule_in_station_override_violates_the_contract(repo: Path) -> None:
    with pytest.raises(ContractError):
        pilot(repo, stations=[{"location": "A", "overrides": {"regra_x": {"enabled": False}}}])


@pytest.fixture
def two_station_batch(tmp_path: Path) -> Path:
    """Um documento por estação, cada um com uma página em branco; um terceiro sem equipamento."""
    root = tmp_path / "lote"
    for doc, model in (("A", "i4250"), ("B", "S2085f"), ("C", "desconhecido")):
        for i in range(1, 4):
            save(root / doc / f"{i:04d}.tif", page_150(10 * ord(doc) + i, i), model=model)
        save(root / doc / "0004.tif", blank_150(ord(doc)), model=model)
    return root


def station_profile(repo: Path) -> Profile:
    return pilot(
        repo,
        resolution={"min_dpi": 150},
        numbering={"enabled": False},
        stations=[
            {"id": "cg-e3", "make": "Kodak", "model": "i4250", "location": "Estação 3"},
            {
                "id": "centro-e1",
                "make": "Kodak",
                "model": "S2085f",
                "location": "Estação 1",
                "overrides": {"blank_page": {"enabled": False}},
            },
        ],
    )


def test_each_page_is_judged_with_its_station_settings(repo: Path, two_station_batch: Path) -> None:
    report = analysis_json(run_analysis(two_station_batch, station_profile(repo), workers=1))
    pages = {p["id"]: p for p in report["pages"]}
    by_doc = {p["source_file"].split("/")[0]: p["station_id"] for p in report["pages"]}
    assert by_doc == {"A": "cg-e3", "B": "centro-e1", "C": None}
    blank = sorted(
        pages[f["target"]["id"]]["source_file"]
        for f in report["findings"]
        if f["rule"] == "blank_page"
    )
    assert blank == ["A/0004.tif", "C/0004.tif"]  # a estação do documento B desliga a regra


def test_fallback_station_applies_when_the_file_does_not_say(
    repo: Path, two_station_batch: Path
) -> None:
    profile = station_profile(repo)
    report = analysis_json(
        run_analysis(two_station_batch, profile, workers=1, fallback_station="centro-e1")
    )
    by_doc = {p["source_file"].split("/")[0]: p for p in report["pages"]}
    assert by_doc["C"]["station_id"] == "centro-e1" and by_doc["C"]["station"] == "Estação 1"
    assert by_doc["A"]["station_id"] == "cg-e3"  # o equipamento do arquivo tem prioridade
    pages = {p["id"]: p for p in report["pages"]}
    blank = [
        pages[f["target"]["id"]]["source_file"]
        for f in report["findings"]
        if f["rule"] == "blank_page"
    ]
    assert blank == ["A/0004.tif"]
    unknown = analysis_json(
        run_analysis(two_station_batch, profile, workers=1, fallback_station="nao-existe")
    )
    assert {p["station_id"] for p in unknown["pages"] if p["source_file"].startswith("C/")} == {
        None
    }
