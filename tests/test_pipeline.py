from backend.pipeline import ContextRecoveryPipeline
from backend.reasoning.context_engine import ProjectContext
from backend.schemas import (
    Decision,
    DecisionStatus,
    Evidence,
    EvidenceType,
    Event,
    EventType,
)
from datetime import datetime, timezone


def make_event(
    event_id: str,
    content: str,
    title: str | None = None,
):
    return Event(
        id=event_id,
        source="test",
        source_id=event_id,
        event_type=EventType.MESSAGE,
        actor="member-1",
        timestamp=datetime.now(timezone.utc),
        project="RETRO-AI",
        title=title,
        content=content,
    )


def make_context():
    return ProjectContext(
        project="RETRO-AI",
        summary="Project context recovery system.",
        current_state="Core processing pipeline is implemented.",
        completed_work=[
            "GitHub ingestion",
            "Normalization",
        ],
        active_work=[
            "Context reconstruction",
        ],
        blocked_work=[
            "LLM integration",
        ],
        planned_work=[
            "Dashboard",
        ],
        abandoned_work=[],
        unknown_work=[],
        important_decisions=[
            "Use n8n as orchestration layer.",
        ],
        dependencies=[
            "GitHub",
            "Project documentation",
        ],
        risks=[],
        evidence_ids=[
            "evidence-1",
        ],
    )


def test_pipeline_generates_takeover_report():

    event = make_event(
        "event-1",
        "We decided to use n8n as the orchestration layer.",
        "Architecture decision",
    )

    evidence = Evidence(
        id="evidence-1",
        evidence_type=EvidenceType.DECISION,
        claim="Use n8n as orchestration layer.",
        description="Architecture decision.",
        source_event_ids=["event-1"],
        confidence=0.95,
        project="RETRO-AI",
    )

    pipeline = ContextRecoveryPipeline()

    result = pipeline.run(
        events=[event],
        evidence=[evidence],
        context=make_context(),
        target_role="Backend Developer",
        previous_owner="member-2",
    )

    assert result.context is not None
    assert result.takeover_report is not None

    assert result.takeover_report.project == "RETRO-AI"
    assert (
        result.takeover_report.target_role
        == "Backend Developer"
    )

    assert (
        result.takeover_report.previous_owner
        == "member-2"
    )

    assert len(result.decisions) == 1

    assert (
        result.decisions[0].status
        == DecisionStatus.PROPOSED
    )


def test_pipeline_accepts_existing_decisions():

    event = make_event(
        "event-2",
        "Some project update.",
    )

    evidence = Evidence(
        id="evidence-2",
        evidence_type=EvidenceType.FACT,
        claim="Project update.",
        source_event_ids=["event-2"],
        confidence=0.9,
        project="RETRO-AI",
    )

    decision = Decision(
        id="decision-1",
        title="Use Python",
        decision="Use Python for backend.",
        problem=None,
        alternatives=[],
        reason=None,
        status=DecisionStatus.ACCEPTED,
        evidence_ids=["evidence-2"],
        decided_by=["member-1"],
        project="RETRO-AI",
    )

    pipeline = ContextRecoveryPipeline()

    result = pipeline.run(
        events=[event],
        evidence=[evidence],
        context=make_context(),
        decisions=[decision],
        target_role="Developer",
    )

    assert len(result.decisions) == 1

    assert result.decisions[0].id == "decision-1"

    assert (
        result.takeover_report is not None
    )