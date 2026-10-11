from datetime import datetime, timezone

from backend.processing import DependencyEngine
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
    references: list[str] | None = None,
    content: str = "",
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
        project="test/project",
        title=title,
        content=content,
        url=f"https://github.com/test/{event_id}",
        references=references or [],
        metadata=metadata or {},
    )


def test_explicit_event_reference_creates_dependency():

    issue = make_event(
        "github_issue_123",
        event_type=EventType.ISSUE,
        title="API failure",
        metadata={"number": 123},
    )

    commit = make_event(
        "commit_1",
        title="Fix API failure",
        references=["issue:123"],
    )

    graph = DependencyEngine().build(
        [issue, commit]
    )

    assert len(graph.dependencies) == 1

    dependency = graph.dependencies[0]

    assert dependency.source_id == "commit_1"
    assert dependency.target_id == "github_issue_123"
    assert dependency.dependency_type == "references"
    assert dependency.confidence == 0.95


def test_unknown_reference_is_ignored():

    event = make_event(
        "commit_1",
        references=["issue:999"],
    )

    graph = DependencyEngine().build([event])

    assert graph.dependencies == []


def test_self_reference_is_ignored():

    event = make_event(
        "event_1",
        references=["event_1"],
    )

    graph = DependencyEngine().build([event])

    assert graph.dependencies == []


def test_evidence_dependency_creates_relationship():

    event_a = make_event(
        "task_a",
        title="Deploy service",
    )

    event_b = make_event(
        "task_b",
        title="Build service",
    )

    evidence = Evidence(
        id="evidence_task_a_dependency",
        evidence_type=EvidenceType.DEPENDENCY,
        claim="Deployment depends on task_b",
        description="Deploy service depends on task_b",
        source_event_ids=["task_a"],
        confidence=0.8,
    )

    graph = DependencyEngine().build(
        [event_a, event_b],
        [evidence],
    )

    assert len(graph.dependencies) == 1

    dependency = graph.dependencies[0]

    assert dependency.source_id == "task_a"
    assert dependency.target_id == "task_b"
    assert dependency.dependency_type == "evidence_dependency"
    assert dependency.confidence == 0.8
    assert dependency.evidence_ids == [
        "evidence_task_a_dependency"
    ]


def test_dependency_graph_queries():

    dependencies = [
        {
            "source_id": "task_a",
            "target_id": "task_b",
            "dependency_type": "references",
            "reason": "A references B",
            "confidence": 0.9,
        },
        {
            "source_id": "task_c",
            "target_id": "task_b",
            "dependency_type": "references",
            "reason": "C references B",
            "confidence": 0.9,
        },
    ]

    from backend.processing.dependencies import (
        Dependency,
        DependencyGraph,
    )

    graph = DependencyGraph(
        [
            Dependency(**item)
            for item in dependencies
        ]
    )

    assert len(
        graph.get_dependencies_of("task_a")
    ) == 1

    assert len(
        graph.get_dependents_of("task_b")
    ) == 2


def test_duplicate_dependencies_are_removed():

    issue = make_event(
        "github_issue_123",
        event_type=EventType.ISSUE,
        metadata={"number": 123},
    )

    commit = make_event(
        "commit_1",
        references=[
            "issue:123",
            "issue:123",
        ],
    )

    graph = DependencyEngine().build(
        [issue, commit]
    )

    assert len(graph.dependencies) == 1


def test_empty_dependency_graph():

    graph = DependencyEngine().build([])

    assert graph.dependencies == []
    assert graph.to_list() == []


def test_dependency_to_dict():

    issue = make_event(
        "github_issue_123",
        event_type=EventType.ISSUE,
        metadata={"number": 123},
    )

    commit = make_event(
        "commit_1",
        references=["issue:123"],
    )

    graph = DependencyEngine().build(
        [issue, commit]
    )

    result = graph.to_list()

    assert len(result) == 1
    assert result[0]["source_id"] == "commit_1"
    assert result[0]["target_id"] == "github_issue_123"