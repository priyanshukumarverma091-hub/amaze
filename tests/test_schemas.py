from datetime import datetime, timezone

from backend.schemas import (
    Decision,
    DecisionStatus,
    Event,
    EventType,
    Evidence,
    EvidenceType,
    TakeoverReport,
    WorkItem,
    WorkStatus,
)


def test_event():
    event = Event(
        id="evt_001",
        source="github",
        source_id="abc123",
        event_type=EventType.COMMIT,
        actor="member_1",
        timestamp=datetime.now(timezone.utc),
        project="context-recovery-engine",
        title="Add authentication",
        content="Implemented authentication flow.",
    )

    assert event.source == "github"
    assert event.event_type == EventType.COMMIT


def test_evidence():
    evidence = Evidence(
        id="ev_001",
        evidence_type=EvidenceType.DECISION,
        claim="Team selected OAuth authentication.",
        confidence=0.95,
        source_event_ids=["evt_001"],
    )

    assert evidence.confidence == 0.95


def test_decision():
    decision = Decision(
        id="dec_001",
        title="Authentication strategy",
        decision="Use OAuth",
        problem="Need secure authentication.",
        alternatives=["JWT only", "OAuth"],
        reason="Better security and integration.",
        status=DecisionStatus.ACCEPTED,
        evidence_ids=["ev_001"],
        decided_by=["member_1"],
    )

    assert decision.status == DecisionStatus.ACCEPTED


def test_takeover():
    work = WorkItem(
        title="Authentication",
        description="Implement OAuth integration.",
        status=WorkStatus.DONE,
        evidence_ids=["ev_001"],
    )

    report = TakeoverReport(
        id="takeover_001",
        project="context-recovery-engine",
        target_role="Backend Developer",
        project_summary="Team knowledge recovery system.",
        current_state="Authentication is implemented.",
        completed_work=[work],
        recommended_first_steps=["Review authentication architecture."],
    )

    assert report.target_role == "Backend Developer"
    assert len(report.completed_work) == 1