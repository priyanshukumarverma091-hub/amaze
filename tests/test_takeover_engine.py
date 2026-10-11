from datetime import datetime, timezone

from backend.reasoning.takeover_engine import TakeoverEngine
from backend.reasoning.context_engine import ProjectContext
from backend.schemas import Decision, DecisionStatus


def make_context() -> ProjectContext:
    return ProjectContext(
        project="RETRO-AI",
        summary="AI project for recovering project context.",
        current_state="Core processing pipeline is implemented.",
        completed_work=[
            "GitHub ingestion",
            "Normalization",
            "Deduplication",
        ],
        active_work=[
            "Context reconstruction",
        ],
        blocked_work=[
            "LLM integration",
        ],
        planned_work=[
            "Takeover dashboard",
        ],
        abandoned_work=[],
        unknown_work=[],
        important_decisions=[
            "Use n8n as the orchestration layer.",
        ],
        dependencies=[
            "GitHub repository",
            "Project documentation",
        ],
        risks=[],
        evidence_ids=[
            "event-001",
            "event-002",
        ],
    )


def test_takeover_engine_generates_report():

    context = make_context()

    decision = Decision(
        id="decision-001",
        title="Orchestration",
        decision="Use n8n as the orchestration layer.",
        problem="Need a workflow orchestration system.",
        alternatives=["Custom Python workflow"],
        reason="Workflow automation requirement.",
        status=DecisionStatus.ACCEPTED,
        evidence_ids=["event-003"],
        decided_by=["team"],
        project="RETRO-AI",
    )

    engine = TakeoverEngine()

    report = engine.generate(
        context=context,
        decisions=[decision],
        target_role="Backend Developer",
        previous_owner="member-2",
    )

    assert report.project == "RETRO-AI"
    assert report.target_role == "Backend Developer"
    assert report.previous_owner == "member-2"

    assert len(report.completed_work) == 3
    assert len(report.active_work) == 1
    assert len(report.blocked_work) == 1

    assert report.completed_work[0].status.value == "done"
    assert report.active_work[0].status.value == "in_progress"
    assert report.blocked_work[0].status.value == "blocked"

    assert "GitHub repository" in report.dependencies

    assert any(
        "Orchestration" in decision
        for decision in report.important_decisions
    )

    assert "event-001" in report.evidence_ids
    assert "event-003" in report.evidence_ids

    assert len(report.recommended_first_steps) > 0


def test_takeover_engine_without_decisions():

    context = make_context()

    engine = TakeoverEngine()

    report = engine.generate(
        context=context,
        target_role="ML Engineer",
    )

    assert report.project == "RETRO-AI"
    assert report.target_role == "ML Engineer"
    assert report.previous_owner is None

    assert len(report.important_decisions) > 0
    assert len(report.recommended_first_steps) > 0


def test_takeover_engine_empty_context():

    context = ProjectContext(
        project="Empty Project",
        summary="No data available.",
        current_state="Unknown.",
        completed_work=[],
        active_work=[],
        blocked_work=[],
        planned_work=[],
        abandoned_work=[],
        unknown_work=[],
        important_decisions=[],
        dependencies=[],
        risks=[],
        evidence_ids=[],
    )

    engine = TakeoverEngine()

    report = engine.generate(
        context=context,
        target_role="Developer",
    )

    assert report.project == "Empty Project"
    assert report.target_role == "Developer"
    assert report.previous_owner is None
    assert report.completed_work == []
    assert report.active_work == []
    assert report.blocked_work == []
    assert len(report.recommended_first_steps) > 0