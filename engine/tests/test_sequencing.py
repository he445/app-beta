import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from qa_engine.detectors.sequence import analyze_document
from qa_engine.domain.sequencing import (
    Folio,
    Mark,
    NumberingMode,
    PageCandidates,
    PageNumberingState,
    Reading,
    SequenceParams,
    missing_between,
    parse_folio,
    resolve,
    successor,
)


def pages_from(readings: list[str | None], conf: float = 0.95) -> list[PageCandidates]:
    return [
        PageCandidates(f"p{i}", (Mark((Reading(r, conf),)),) if r is not None else ())
        for i, r in enumerate(readings)
    ]


@pytest.mark.parametrize(
    ("text", "folio"),
    [
        ("12", Folio(12)),
        ("fls. 12", Folio(12)),
        ("12v", Folio(12, verso=True)),
        ("12-v", Folio(12, verso=True)),
        ("12-A", Folio(12, "A")),
        ("12a", Folio(12, "A")),
        ("12-Av", Folio(12, "A", True)),
        ("abc", None),
        ("", None),
    ],
)
def test_parse_folio(text: str, folio: Folio | None) -> None:
    assert parse_folio(text) == folio


def test_successor_and_missing_recto_verso() -> None:
    mode = NumberingMode.RECTO_VERSO
    assert successor(Folio(3), mode) == Folio(3, verso=True)
    assert successor(Folio(3, verso=True), mode) == Folio(4)
    assert missing_between(Folio(2, verso=True), Folio(4), mode) == [Folio(3), Folio(3, verso=True)]
    assert missing_between(Folio(12), Folio(12, "A"), NumberingMode.SIMPLE) == []


def test_conformance_cases(repo) -> None:  # type: ignore[no-untyped-def]
    cases = json.loads((repo / "conformance/fixtures/sequencing/cases.json").read_text("utf-8"))
    for case in cases["cases"]:
        pages = [
            PageCandidates(
                f"p{i}",
                tuple(
                    Mark(tuple(Reading(t, c) for t, c in m["readings"]), m.get("struck", False))
                    for m in marks
                ),
            )
            for i, marks in enumerate(case["pages"])
        ]
        params = SequenceParams(mode=NumberingMode(case["mode"]))
        result, flags = analyze_document("doc", pages, params)
        exp = case["expected"]
        by_id = {p.page_id: p for p in result.pages}
        ordered = [by_id[pid] for pid in result.order]
        assert [p.state.value for p in ordered] == exp["states"], case["id"]
        assert [str(p.value) if p.value else None for p in ordered] == exp["values"], case["id"]
        assert result.reordered == exp["reordered"], case["id"]
        assert [[str(f) for f in g.missing] for g in result.gaps] == exp["gaps"], case["id"]
        assert sorted({f.rule for f in flags}) == sorted(set(exp["rules"])), case["id"]
        if "order" in exp:
            assert list(result.order) == [f"p{i}" for i in exp["order"]], case["id"]
        if "previous" in exp:
            assert [list(p.previous) for p in ordered] == exp["previous"], case["id"]


def test_declared_count_short_is_missing_page() -> None:
    _, flags = analyze_document("doc", pages_from([None, None]), SequenceParams(), 3)
    assert [(f.rule, f.flag.measure) for f in flags] == [("missing_page", 1.0)]


def test_duplicate_copy_does_not_reorder_or_repeat() -> None:
    pages = pages_from(["1", "2", "3", "2"])
    _, flags = analyze_document("doc", pages, SequenceParams(), duplicates={"p3": "p1"})
    assert flags == []


@settings(max_examples=60, deadline=None)
@given(
    n=st.integers(min_value=3, max_value=40),
    drops=st.sets(st.integers(min_value=1, max_value=38), max_size=4),
    start=st.integers(min_value=1, max_value=500),
)
def test_confident_gaps_are_found_exactly(n: int, drops: set[int], start: int) -> None:
    """Com leituras confiáveis, cada folha removida do meio vira exatamente uma lacuna."""
    drops = {d for d in drops if 0 < d < n - 1}
    folios = [start + i for i in range(n) if i not in drops]
    result = resolve(pages_from([str(f) for f in folios]), SequenceParams())
    missing = sorted(f.number for g in result.gaps for f in g.missing)
    assert missing == sorted(start + d for d in drops)
    assert all(g.confirmed for g in result.gaps)
    assert all(p.state is PageNumberingState.READ for p in result.pages)


@settings(max_examples=60, deadline=None)
@given(
    n=st.integers(min_value=3, max_value=30),
    wrong=st.integers(min_value=1, max_value=28),
    offset=st.integers(min_value=3, max_value=90),
)
def test_isolated_misread_is_corrected_by_context(n: int, wrong: int, offset: int) -> None:
    """Uma leitura errada de baixa confiança no meio é inferida pelo contexto."""
    wrong = min(wrong, n - 2)
    pages = pages_from([str(i + 1) for i in range(n)])
    pages[wrong] = PageCandidates(
        pages[wrong].page_id, (Mark((Reading(str(wrong + 1 + offset), 0.6),)),)
    )
    result = resolve(pages, SequenceParams())
    page = result.pages[wrong]
    assert page.state is PageNumberingState.INFERRED
    assert page.value == Folio(wrong + 1)
    assert result.gaps == ()


def test_resolver_is_deterministic() -> None:
    pages = pages_from(["1", "3", None, "2", "9", "5"], conf=0.7)
    assert resolve(pages, SequenceParams()) == resolve(pages, SequenceParams())


# Checagem de documento: troca sistemática de dígito (P4 do relatório de testes) ------


@settings(max_examples=60, deadline=None)
@given(n=st.integers(min_value=2, max_value=60))
def test_document_starting_at_one_is_never_doubted(n: int) -> None:
    """Começando em fls. 1, nenhum dígito é comum a todas as folhas: sem dúvida."""
    from qa_engine.domain.sequencing import document_doubt

    result = resolve(pages_from([str(i + 1) for i in range(n)]), SequenceParams())
    assert document_doubt(result, SequenceParams()) is None


@settings(max_examples=60, deadline=None)
@given(decade=st.integers(min_value=1, max_value=99), n=st.integers(min_value=2, max_value=10))
def test_shared_digit_with_a_lower_swap_is_doubted(decade: int, n: int) -> None:
    """Todas as folhas na mesma dezena: dúvida se a tabela troca a dezena por um dígito menor."""
    from qa_engine.domain.sequencing import DIGIT_CONFUSIONS, document_doubt

    folios = [decade * 10 + i for i in range(n)]
    result = resolve(pages_from([str(f) for f in folios]), SequenceParams())
    doubt = document_doubt(result, SequenceParams())
    tens = str(decade)[-1]
    leading = decade < 10  # a dezena é a primeira casa: trocar por 0 daria "0x"
    lower = any(r == tens and a < tens and not (leading and a == "0") for r, a in DIGIT_CONFUSIONS)
    if lower:
        assert doubt is not None and doubt.alternative_first is not None
        assert doubt.alternative_last is not None
        shift = doubt.alternative_first.number - folios[0]
        assert shift < 0 and doubt.alternative_last.number - folios[-1] == shift
    elif leading:
        assert doubt is None


def test_consistent_misread_document_goes_to_review() -> None:
    """1920–1925 lido como 1990–1995 com confiança alta: o documento vai para revisão."""
    from qa_engine.detectors.sequence import analyze_document
    from qa_engine.domain.sequencing import document_doubt

    pages = pages_from(["1990", "1991", "1992", "1993", "1994", "1995"], conf=0.98)
    result, flags = analyze_document("doc", pages, SequenceParams())
    assert all(p.state is PageNumberingState.READ for p in result.pages)
    doubt = document_doubt(result, SequenceParams())
    assert doubt is not None and (doubt.read, doubt.alternative) == ("9", "2")
    assert str(doubt.alternative_first) == "1920" and str(doubt.alternative_last) == "1925"
    assert [f.rule for f in flags] == ["numbering_review"]
    assert flags[0].target.id == result.order[0]
    assert "também fecha como fls. 1920 a 1925" in flags[0].flag.message
    # Sem tabela de trocas, nada; com início máximo, a dúvida volta pelo salto.
    off = SequenceParams(confusions=())
    assert document_doubt(result, off) is None
    start = document_doubt(result, SequenceParams(confusions=(), max_first_folio=10))
    assert start is not None and start.alternative is None
    _, flags = analyze_document("doc", pages, SequenceParams(confusions=(), max_first_folio=10))
    assert "começa em fls. 1990" in flags[0].flag.message


def test_swap_to_a_leading_zero_is_not_an_alternative() -> None:
    """9 → 0 na primeira casa daria "0x": ninguém escreve folha com zero à esquerda."""
    from qa_engine.domain.sequencing import document_doubt

    result = resolve(pages_from(["91", "92", "93"]), SequenceParams())
    doubt = document_doubt(result, SequenceParams(confusions=(("9", "0"),)))
    assert doubt is None
