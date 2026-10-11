from datetime import datetime, timezone

from backend.processing import (
    Dependency,
    DependencyGraph,
)
from backend.processing.timeline import TimelineEngine
from backend.reasoning import ContextEngine
from backend.schemas import (
    Event,
    EventType,
    Evidence,
    EvidenceType,
)


def make_event(
    event_id: str,
    event_type: EventType = EventType.COMMIT,
    title: str = "Test event",
    content: str = "",
    project: str = "test/project",
    metadata: dict | None = None,
) -> Event:

    return Event(
        id=event_id,
        source="github",
        source_id=event_id,
        event_type=event_type,
        actor="developer",
        timestamp=datetime(
            2026,
            9,
            25,
            tzinfo=timezone.utc,
        ),
        project=project,
        title=title,
        content=content,
        url=f"https://github.com/test/{event_id}",
        metadata=metadata or {},
    )


def build_context(
    events,
    evidence=None,
    dependencies=None,
):

    evidence = evidence or []

    timeline = TimelineEngine().build(
        events,
        evidence,
    )

    graph = DependencyGraph(
        dependencies or []
    )

    return ContextEngine().build(
        events=events,
        evidence=evidence,
        timeline=timeline,
        dependencies=graph,
    )


def test_completed_commit_is_detected():

    event = make_event(
        "commit_1",
        title="Implement login",
    )

    context = build_context([event])

    assert context.current_state == "completed"

    assert len(
        context.completed_work
    ) == 1

    assert (
        context.completed_work[0].event_id
        == "commit_1"
    )


def test_merged_pr_is_completed():

    event = make_event(
        "pr_1",
        event_type=EventType.PULL_REQUEST,
        title="Add authentication",
        metadata={
            "merged": True,
            "state": "closed",
        },
    )

    context = build_context([event])

    assert len(
        context.completed_work
    ) == 1

    assert (
        context.completed_work[0].status
        == "done"
    )


def test_open_issue_is_unknown_by_default():

    event = make_event(
        "issue_1",
        event_type=EventType.ISSUE,
        title="API failure",
        metadata={
            "state": "open",
        },
    )

    context = build_context([event])

    assert len(
        context.unknown_work
    ) == 1

    assert (
        context.unknown_work[0].status
        == "unknown"
    )


def test_blocked_work_is_detected():

    event = make_event(
        "task_1",
        event_type=EventType.TASK,
        title="Deploy API",
        content="Deployment is blocked by task_2.",
    )

    context = build_context([event])

    assert context.current_state == "blocked"

    assert len(
        context.blocked_work
    ) == 1


def test_planned_work_is_detected():

    event = make_event(
        "task_1",
        event_type=EventType.TASK,
        title="Add dashboard",
        content="We plan to implement the dashboard.",
    )

    context = build_context([event])

    assert context.current_state == "planned"

    assert len(
        context.planned_work
    ) == 1


def test_decisions_are_preserved():

    event = make_event(
        "event_1",
        title="Architecture decision",
        content="We decided to use PostgreSQL.",
    )

    evidence = [
        Evidence(
            id="evidence_decision_1",
            evidence_type=EvidenceType.DECISION,
            claim="Possible decision: Architecture decision",
            description=event.content,
            source_event_ids=["event_1"],
            confidence=0.7,
            project="test/project",
        )
    ]

    context = build_context(
        [event],
        evidence,
    )

    assert len(
        context.important_decisions
    ) == 1

    assert (
        context.important_decisions[0].id
        == "evidence_decision_1"
    )


def test_dependencies_are_preserved():

    event_a = make_event(
        "task_a",
        title="Deploy application",
    )

    event_b = make_event(
        "task_b",
        title="Build application",
    )

    dependency = Dependency(
        source_id="task_a",
        target_id="task_b",
        dependency_type="references",
        reason="Deployment depends on build.",
        confidence=0.9,
    )

    context = build_context(
        [event_a, event_b],
        dependencies=[dependency],
    )

    assert len(
        context.dependencies
    ) == 1

    assert (
        context.dependencies[0]["source_id"]
        == "task_a"
    )


def test_context_items_keep_evidence_ids():

    event = make_event(
        "event_1",
        title="Fix bug",
    )

    evidence = Evidence(
        id="evidence_1",
        evidence_type=EvidenceType.SOLUTION,
        claim="Possible solution: Fix bug",
        description="Bug fixed.",
        source_event_ids=["event_1"],
        confidence=0.8,
    )

    context = build_context(
        [event],
        [evidence],
    )

    item = context.completed_work[0]

    assert item.evidence_ids == [
        "evidence_1"
    ]

    assert item.confidence == 0.8


def test_risk_is_detected_for_blocked_work():

    event = make_event(
        "task_1",
        event_type=EventType.TASK,
        title="Deploy service",
        content="Deployment is blocked.",
    )

    context = build_context([event])

    assert any(
        "Blocked work" in risk
        for risk in context.risks
    )


def test_project_is_detected():

    events = [
        make_event(
            "event_1",
            project="project/a",
        ),
        make_event(
            "event_2",
            project="project/a",
        ),
        make_event(
            "event_3",
            project="project/b",
        ),
    ]

    context = build_context(events)

    assert context.project == "project/a"


def test_summary_is_generated():

    event = make_event(
        "event_1",
        title="Implement API",
    )

    context = build_context([event])

    assert "test/project" in context.summary
    assert "1 tracked events" in context.summary
    assert "1 items are completed" in context.summary


def test_empty_context():

    context = build_context([])

    assert context.project == "unknown"
    assert context.current_state == "unknown"
    assert context.completed_work == []
    assert context.active_work == []
    assert context.blocked_work == []
    assert context.planned_work == []
    assert context.risks == []


def test_context_to_dict():

    event = make_event(
        "event_1",
        title="Implement API",
    )

    context = build_context([event])

    result = context.to_dict()

    assert result["project"] == "test/project"
    assert result["current_state"] == "completed"
    assert len(result["completed_work"]) == 1
    assert "evidence_ids" in result