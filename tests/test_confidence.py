from datetime import datetime, timedelta, timezone

from backend.reasoning import (
    ConfidenceEngine,
    ConfidenceResult,
)
from backend.reasoning.conflict_detector import Conflict
from backend.schemas import (
    Decision,
    Evidence,
    EvidenceType,
    Event,
    EventType,
)


def make_event(
    event_id="event_1",
    source="github",
    days_old=1,
):
    timestamp = (
        datetime.now(timezone.utc)
        - timedelta(days=days_old)
    )

    return Event(
        id=event_id,
        source=source,
        source_id=event_id,
        event_type=EventType.COMMIT,
        actor="developer",
        timestamp=timestamp,
        project="test/project",
        title="Test event",
        content="Test project change",
        url="https://example.com",
    )


def make_evidence(
    evidence_id="evidence_1",
    event_id="event_1",
    confidence=0.90,
):
    return Evidence(
        id=evidence_id,
        evidence_type=EvidenceType.FACT,
        claim="Test fact",
        description="Test evidence",
        source_event_ids=[event_id],
        confidence=confidence,
        project="test/project",
    )


def test_high_confidence_evidence():

    event = make_event()

    evidence = make_evidence(
        confidence=0.95
    )

    engine = ConfidenceEngine()

    result = engine.evaluate_evidence(
        evidence,
        [event],
    )

    assert isinstance(
        result,
        ConfidenceResult,
    )

    assert result.score > 0.75

    assert result.level in {
        "high",
        "very_high",
    }


def test_low_confidence_evidence():

    event = make_event(
        source="unknown"
    )

    evidence = make_evidence(
        confidence=0.20
    )

    engine = ConfidenceEngine()

    result = engine.evaluate_evidence(
        evidence,
        [event],
    )

    assert result.score < 0.60

    assert result.level in {
        "low",
        "very_low",
        "medium",
    }


def test_github_source_is_high_reliability():

    engine = ConfidenceEngine()

    score = engine.source_reliability(
        "github"
    )

    assert score == 0.95


def test_discord_source_is_lower_than_github():

    engine = ConfidenceEngine()

    github_score = (
        engine.source_reliability(
            "github"
        )
    )

    discord_score = (
        engine.source_reliability(
            "discord"
        )
    )

    assert github_score > discord_score


def test_unknown_source_is_conservative():

    engine = ConfidenceEngine()

    score = engine.source_reliability(
        "some_unknown_source"
    )

    assert score == 0.50


def test_multiple_sources_increase_agreement():

    event_1 = make_event(
        event_id="event_1",
        source="github",
    )

    event_2 = make_event(
        event_id="event_2",
        source="slack",
    )

    evidence = Evidence(
        id="evidence_1",
        evidence_type=EvidenceType.FACT,
        claim="Shared project fact",
        description="Confirmed by multiple sources",
        source_event_ids=[
            "event_1",
            "event_2",
        ],
        confidence=0.90,
        project="test/project",
    )

    engine = ConfidenceEngine()

    score = engine.cross_source_agreement(
        evidence,
        [
            event_1,
            event_2,
        ],
    )

    assert score == 0.85


def test_three_sources_have_high_agreement():

    events = [
        make_event(
            event_id="event_1",
            source="github",
        ),
        make_event(
            event_id="event_2",
            source="slack",
        ),
        make_event(
            event_id="event_3",
            source="discord",
        ),
    ]

    evidence = Evidence(
        id="evidence_1",
        evidence_type=EvidenceType.FACT,
        claim="Confirmed fact",
        description="Multiple independent sources",
        source_event_ids=[
            "event_1",
            "event_2",
            "event_3",
        ],
        confidence=0.90,
        project="test/project",
    )

    engine = ConfidenceEngine()

    score = engine.cross_source_agreement(
        evidence,
        events,
    )

    assert score == 1.0


def test_single_source_has_lower_agreement():

    event = make_event()

    evidence = make_evidence()

    engine = ConfidenceEngine()

    score = engine.cross_source_agreement(
        evidence,
        [event],
    )

    assert score == 0.60


def test_recent_evidence_has_high_recency():

    event = make_event(
        days_old=1
    )

    evidence = make_evidence()

    engine = ConfidenceEngine()

    score = engine.recency_score(
        evidence,
        [event],
    )

    assert score == 1.0


def test_old_evidence_has_lower_recency():

    event = make_event(
        days_old=400
    )

    evidence = make_evidence()

    engine = ConfidenceEngine()

    score = engine.recency_score(
        evidence,
        [event],
    )

    assert score == 0.30


def test_evidence_strength_uses_confidence():

    engine = ConfidenceEngine()

    evidence = make_evidence(
        confidence=0.80
    )

    score = engine.evidence_strength(
        evidence
    )

    assert score == 0.80


def test_multiple_evidence_sources_strengthen_evidence():

    evidence = Evidence(
        id="evidence_1",
        evidence_type=EvidenceType.FACT,
        claim="Strong fact",
        description="Supported by multiple events",
        source_event_ids=[
            "event_1",
            "event_2",
            "event_3",
        ],
        confidence=0.80,
        project="test/project",
    )

    engine = ConfidenceEngine()

    score = engine.evidence_strength(
        evidence
    )

    assert score == 0.90


def test_conflict_penalty():

    evidence = make_evidence()

    conflict = Conflict(
        conflict_id="conflict_1",
        conflict_type="contradictory_decisions",
        description="Conflicting decisions",
        decision_ids=[
            "decision_1",
            "decision_2",
        ],
        evidence_ids=[
            "evidence_1",
        ],
        confidence=0.85,
    )

    engine = ConfidenceEngine()

    penalty = engine.conflict_penalty(
        evidence,
        [conflict],
    )

    assert penalty == 0.15


def test_no_conflict_has_zero_penalty():

    evidence = make_evidence()

    engine = ConfidenceEngine()

    penalty = engine.conflict_penalty(
        evidence,
        [],
    )

    assert penalty == 0.0


def test_confidence_level_very_high():

    assert (
        ConfidenceEngine.confidence_level(
            0.95
        )
        == "very_high"
    )


def test_confidence_level_high():

    assert (
        ConfidenceEngine.confidence_level(
            0.80
        )
        == "high"
    )


def test_confidence_level_medium():

    assert (
        ConfidenceEngine.confidence_level(
            0.60
        )
        == "medium"
    )


def test_confidence_level_low():

    assert (
        ConfidenceEngine.confidence_level(
            0.40
        )
        == "low"
    )


def test_confidence_level_very_low():

    assert (
        ConfidenceEngine.confidence_level(
            0.20
        )
        == "very_low"
    )


def test_result_to_dict():

    event = make_event()

    evidence = make_evidence()

    engine = ConfidenceEngine()

    result = engine.evaluate_evidence(
        evidence,
        [event],
    )

    data = result.to_dict()

    assert isinstance(
        data,
        dict,
    )

    assert "score" in data
    assert "level" in data
    assert "factors" in data
    assert "evidence_ids" in data
    assert "warnings" in data


def test_decision_without_evidence_has_zero_confidence():

    decision = Decision(
        id="decision_1",
        title="Architecture",
        decision="Use PostgreSQL",
        evidence_ids=[],
        decided_by=["developer"],
        project="test/project",
    )

    engine = ConfidenceEngine()

    result = engine.evaluate_decision(
        decision=decision,
        evidence=[],
        events=[],
        conflicts=[],
    )

    assert result.score == 0.0

    assert result.level == "very_low"

    assert (
        "Decision has no linked evidence."
        in result.warnings
    )


def test_decision_confidence_from_evidence():

    event = make_event()

    evidence = make_evidence(
        confidence=0.95
    )

    decision = Decision(
        id="decision_1",
        title="Architecture",
        decision="Use PostgreSQL",
        evidence_ids=[
            "evidence_1"
        ],
        decided_by=["developer"],
        project="test/project",
    )

    engine = ConfidenceEngine()

    result = engine.evaluate_decision(
        decision=decision,
        evidence=[evidence],
        events=[event],
        conflicts=[],
    )

    assert result.score > 0.70

    assert (
        "evidence_1"
        in result.evidence_ids
    )


def test_multiple_decision_evidence_is_averaged():

    event_1 = make_event(
        event_id="event_1",
        source="github",
    )

    event_2 = make_event(
        event_id="event_2",
        source="slack",
    )

    evidence_1 = make_evidence(
        evidence_id="evidence_1",
        event_id="event_1",
        confidence=0.90,
    )

    evidence_2 = make_evidence(
        evidence_id="evidence_2",
        event_id="event_2",
        confidence=0.70,
    )

    decision = Decision(
        id="decision_1",
        title="Architecture",
        decision="Use PostgreSQL",
        evidence_ids=[
            "evidence_1",
            "evidence_2",
        ],
        decided_by=["developer"],
        project="test/project",
    )

    engine = ConfidenceEngine()

    result = engine.evaluate_decision(
        decision=decision,
        evidence=[
            evidence_1,
            evidence_2,
        ],
        events=[
            event_1,
            event_2,
        ],
        conflicts=[],
    )

    assert 0.0 < result.score <= 1.0

    assert set(
        result.evidence_ids
    ) == {
        "evidence_1",
        "evidence_2",
    }


def test_conflicting_evidence_reduces_confidence():

    event = make_event()

    evidence = make_evidence(
        confidence=0.95
    )

    conflict = Conflict(
        conflict_id="conflict_1",
        conflict_type="contradictory_decisions",
        description="Conflicting decisions",
        decision_ids=[
            "decision_1",
            "decision_2",
        ],
        evidence_ids=[
            "evidence_1",
        ],
        confidence=0.85,
    )

    engine = ConfidenceEngine()

    without_conflict = (
        engine.evaluate_evidence(
            evidence,
            [event],
            [],
        )
    )

    with_conflict = (
        engine.evaluate_evidence(
            evidence,
            [event],
            [conflict],
        )
    )

    assert (
        with_conflict.score
        < without_conflict.score
    )

    assert (
        "Related conflicting decisions were detected."
        in with_conflict.warnings
    )