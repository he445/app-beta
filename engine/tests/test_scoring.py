from datetime import UTC, datetime

from qa_engine.domain.model import (
    Correction,
    CorrectionAction,
    CorrectionClass,
    Decision,
    DecisionAction,
    DocumentState,
    Finding,
    Severity,
    Target,
    TargetKind,
    Verdict,
)
from qa_engine.domain.scoring import (
    VerdictPolicy,
    batch_verdict,
    document_state,
    green_sample,
    pages_needing_review,
)

NOW = datetime(2026, 11, 5, tzinfo=UTC)


def finding(sev: Severity, target: str = "p1", decision: DecisionAction | None = None) -> Finding:
    return Finding(
        id=f"{target}-{sev}",
        target=Target(TargetKind.PAGE, target),
        rule="blur",
        rule_version="1.0.0",
        severity=sev,
        measure=0.0,
        threshold=1.0,
        confidence=1.0,
        correction=Correction(CorrectionClass.PHYSICAL, CorrectionAction.RESCAN, "x"),
        message="x",
        decision=Decision(decision, NOW, "rev") if decision else None,
    )


def test_document_state_by_worst_pending() -> None:
    assert document_state([]) is DocumentState.GREEN
    assert document_state([finding(Severity.LOW)]) is DocumentState.GREEN
    assert document_state([finding(Severity.HIGH), finding(Severity.LOW)]) is DocumentState.YELLOW
    assert document_state([finding(Severity.CRITICAL)]) is DocumentState.RED
    resolved = finding(Severity.CRITICAL, decision=DecisionAction.APPROVE)
    assert document_state([resolved]) is DocumentState.GREEN
    rejected = finding(Severity.CRITICAL, decision=DecisionAction.REJECT)
    assert document_state([rejected]) is DocumentState.RED


def test_verdict() -> None:
    policy = VerdictPolicy()
    greens = {f"d{i}": DocumentState.GREEN for i in range(100)}
    assert batch_verdict(greens, [], policy) is Verdict.APPROVED
    assert batch_verdict({**greens, "x": DocumentState.RED}, [], policy) is Verdict.REJECTED
    yellow = {**greens, **{f"y{i}": DocumentState.YELLOW for i in range(3)}}
    assert batch_verdict(yellow, [], policy) is Verdict.APPROVED_WITH_RESERVATIONS
    origin = [finding(Severity.HIGH, decision=DecisionAction.SOURCE_DEFECT)]
    assert batch_verdict(greens, origin, policy) is Verdict.APPROVED_WITH_RESERVATIONS


def test_green_sample_is_deterministic_and_sized() -> None:
    docs = [f"doc{i}" for i in range(41)]
    first = green_sample("batch", docs, 0.05)
    assert len(first) == 3  # teto(0,05 × 41)
    assert first == green_sample("batch", list(reversed(docs)), 0.05)
    assert first != green_sample("outro", docs, 0.05)
    assert green_sample("batch", docs, 0) == []


def test_pages_needing_review() -> None:
    pages = ["p1", "p2", "p3"]
    to_doc = {"p1": "d1", "p2": "d1", "p3": "d2"}
    review = pages_needing_review(pages, [finding(Severity.MEDIUM, "p1")], to_doc, [])
    assert review == {"p1"}
    low = pages_needing_review(pages, [finding(Severity.LOW, "p1")], to_doc, [])
    assert low == set()
    sampled = pages_needing_review(pages, [], to_doc, ["d1"])
    assert sampled == {"p1", "p2"}
