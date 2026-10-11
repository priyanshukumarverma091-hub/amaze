from datetime import datetime, timedelta, timezone

from backend.reasoning import DecisionEngine
from backend.schemas import (
    DecisionStatus,
    Event,
    EventType,
    Evidence,
    EvidenceType,
)


def make_event(
    event_id: str,
    title: str,
    content: str,
    event_type: EventType = EventType.MESSAGE,
    timestamp: datetime | None = None,
    actor: str = "developer",
) -> Event:

    return Event(
        id=event_id,
        source="github",
        source_id=event_id,
        event_type=event_type,
        actor=actor,
        timestamp=timestamp
        or datetime(
            2026,
            9,
            25,
            tzinfo=timezone.utc,
        ),
        project="test/project",
        title=title,
        content=content,
        url=f"https://example.com/{event_id}",
    )


def make_decision_evidence(
    event_id: str,
    evidence_id: str = "decision_evidence_1",
) -> Evidence:

    return Evidence(
        id=evidence_id,
        evidence_type=EvidenceType.DECISION,
        claim="Possible decision",
        description="Decision evidence",
        source_event_ids=[event_id],
        confidence=0.8,
        project="test/project",
    )


def test_extract_decision():

    event = make_event(
        "event_1",
        "Database decision",
        "We decided to use PostgreSQL.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert len(decisions) == 1

    decision = decisions[0]

    assert (
        decision.status
        == DecisionStatus.PROPOSED
    )

    assert (
        decision.evidence_ids
        == ["decision_evidence_1"]
    )

    assert (
        decision.decided_by
        == ["developer"]
    )


def test_decision_text_is_extracted():

    event = make_event(
        "event_1",
        "Architecture",
        "The team discussed options. "
        "We decided to use Redis because "
        "the API needs faster responses.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert len(decisions) == 1

    assert (
        "We decided to use Redis"
        in decisions[0].decision
    )


def test_reason_is_extracted():

    event = make_event(
        "event_1",
        "Cache decision",
        "We decided to use Redis because "
        "the API needs faster responses.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert (
        decisions[0].reason
        == "the API needs faster responses"
    )


def test_alternative_is_extracted():

    event = make_event(
        "event_1",
        "Database decision",
        "We decided to use PostgreSQL "
        "instead of MongoDB.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert "MongoDB" in decisions[0].alternatives


def test_merged_pr_is_implemented():

    event = make_event(
        "pr_1",
        "Add Redis cache",
        "We decided to use Redis.",
        event_type=EventType.PULL_REQUEST,
    )

    event.metadata["merged"] = True

    evidence = [
        make_decision_evidence("pr_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert (
        decisions[0].status
        == DecisionStatus.IMPLEMENTED
    )


def test_rejected_decision():

    event = make_event(
        "event_1",
        "Database decision",
        "We decided to reject MongoDB.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert (
        decisions[0].status
        == DecisionStatus.REJECTED
    )


def test_superseded_decision():

    event = make_event(
        "event_1",
        "Architecture",
        "This decision was superseded "
        "and replaced by PostgreSQL.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert (
        decisions[0].status
        == DecisionStatus.SUPERSEDED
    )


def test_non_decision_evidence_is_ignored():

    event = make_event(
        "event_1",
        "Bug",
        "The API is broken.",
    )

    evidence = [
        Evidence(
            id="problem_1",
            evidence_type=EvidenceType.PROBLEM,
            claim="API is broken",
            source_event_ids=["event_1"],
            confidence=0.9,
        )
    ]

    decisions = DecisionEngine().extract_decisions(
        [event],
        evidence,
    )

    assert decisions == []


def test_problem_is_linked_to_decision():

    problem_event = make_event(
        "problem_1",
        "API problem",
        "The API is too slow.",
        timestamp=datetime(
            2026,
            9,
            24,
            tzinfo=timezone.utc,
        ),
    )

    decision_event = make_event(
        "decision_1",
        "API architecture",
        "We decided to use Redis because "
        "the API is too slow.",
        timestamp=datetime(
            2026,
            9,
            25,
            tzinfo=timezone.utc,
        ),
    )

    evidence = [
        Evidence(
            id="problem_evidence",
            evidence_type=EvidenceType.PROBLEM,
            claim="API problem",
            description="The API is too slow.",
            source_event_ids=["problem_1"],
            confidence=0.9,
        ),
        make_decision_evidence(
            "decision_1",
            "decision_evidence",
        ),
    ]

    decisions = DecisionEngine().extract_decisions(
        [problem_event, decision_event],
        evidence,
    )

    assert len(decisions) == 1

    assert (
        decisions[0].problem
        == "API problem"
    )


def test_build_decision_chain():

    decision_event = make_event(
        "decision_1",
        "Cache architecture",
        "We decided to use Redis.",
    )

    implementation_event = make_event(
        "implementation_1",
        "Implement Redis cache",
        "Implemented Redis cache.",
        timestamp=(
            decision_event.timestamp
            + timedelta(days=1)
        ),
    )

    evidence = [
        make_decision_evidence(
            "decision_1",
            "decision_1_evidence",
        ),
        Evidence(
            id="solution_1",
            evidence_type=EvidenceType.SOLUTION,
            claim="Redis cache implemented",
            description="Redis cache was implemented.",
            source_event_ids=["implementation_1"],
            confidence=0.9,
        ),
    ]

    engine = DecisionEngine()

    decisions = engine.extract_decisions(
        [decision_event, implementation_event],
        evidence,
    )

    chains = engine.build_chains(
        decisions,
        [decision_event, implementation_event],
        evidence,
    )

    assert len(chains) == 1

    chain = chains[0]

    assert (
        chain.decision.id
        == decisions[0].id
    )

    assert (
        "implementation_1"
        in chain.implementation_event_ids
    )


def test_decision_chain_to_dict():

    event = make_event(
        "event_1",
        "Database",
        "We decided to use PostgreSQL.",
    )

    evidence = [
        make_decision_evidence("event_1")
    ]

    engine = DecisionEngine()

    decisions = engine.extract_decisions(
        [event],
        evidence,
    )

    chains = engine.build_chains(
        decisions,
        [event],
        evidence,
    )

    result = chains[0].to_dict()

    assert "decision" in result
    assert "problem_evidence" in result
    assert "supporting_evidence" in result
    assert "implementation_event_ids" in result
    assert "result_evidence" in result


def test_duplicate_decisions_are_removed():

    event_1 = make_event(
        "event_1",
        "Database",
        "We decided to use PostgreSQL.",
    )

    event_2 = make_event(
        "event_2",
        "Database choice",
        "We decided to use PostgreSQL.",
    )

    evidence = [
        make_decision_evidence(
            "event_1",
            "evidence_1",
        ),
        make_decision_evidence(
            "event_2",
            "evidence_2",
        ),
    ]

    decisions = DecisionEngine().extract_decisions(
        [event_1, event_2],
        evidence,
    )

    assert len(decisions) == 1


def test_empty_decisions():

    decisions = DecisionEngine().extract_decisions(
        [],
        [],
    )

    assert decisions == []