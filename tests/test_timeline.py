from datetime import datetime, timezone

from backend.processing import TimelineEngine
from backend.schemas import (
    Event,
    EventType,
    Evidence,
    EvidenceType,
)


def make_event(
    event_id: str,
    timestamp: datetime,
    event_type: EventType = EventType.COMMIT,
    title: str = "Test event",
    actor: str = "developer",
    project: str = "test/project",
) -> Event:

    return Event(
        id=event_id,
        source="github",
        source_id=event_id,
        event_type=event_type,
        actor=actor,
        timestamp=timestamp,
        project=project,
        title=title,
        content=title,
        url=f"https://github.com/test/{event_id}",
    )


def test_timeline_sorts_events_chronologically():

    events = [
        make_event(
            "event_3",
            datetime(2026, 9, 30, tzinfo=timezone.utc),
        ),
        make_event(
            "event_1",
            datetime(2026, 9, 25, tzinfo=timezone.utc),
        ),
        make_event(
            "event_2",
            datetime(2026, 9, 27, tzinfo=timezone.utc),
        ),
    ]

    timeline = TimelineEngine().build(events)

    assert [
        item.event_id
        for item in timeline.items
    ] == [
        "event_1",
        "event_2",
        "event_3",
    ]


def test_timeline_preserves_event_information():

    event = make_event(
        "event_1",
        datetime(2026, 9, 25, tzinfo=timezone.utc),
        title="Deploy application",
    )

    timeline = TimelineEngine().build([event])

    item = timeline.items[0]

    assert item.event_id == "event_1"
    assert item.event_type == "commit"
    assert item.title == "Deploy application"
    assert item.actor == "developer"
    assert item.project == "test/project"
    assert item.source == "github"
    assert item.url == "https://github.com/test/event_1"


def test_timeline_links_evidence_to_events():

    event = make_event(
        "event_1",
        datetime(2026, 9, 25, tzinfo=timezone.utc),
    )

    evidence = Evidence(
        id="evidence_event_1_fact",
        evidence_type=EvidenceType.FACT,
        claim="Application deployed",
        description="Deployment commit",
        source_event_ids=["event_1"],
        confidence=0.95,
        project="test/project",
    )

    timeline = TimelineEngine().build(
        [event],
        [evidence],
    )

    item = timeline.items[0]

    assert item.evidence_ids == [
        "evidence_event_1_fact"
    ]


def test_group_by_date():

    events = [
        make_event(
            "event_1",
            datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
        ),
        make_event(
            "event_2",
            datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc),
        ),
        make_event(
            "event_3",
            datetime(2026, 9, 26, 10, 0, tzinfo=timezone.utc),
        ),
    ]

    timeline = TimelineEngine().build(events)

    grouped = timeline.group_by_date()

    assert len(grouped["2026-09-25"]) == 2
    assert len(grouped["2026-09-26"]) == 1


def test_group_by_project():

    events = [
        make_event(
            "event_1",
            datetime(2026, 9, 25, tzinfo=timezone.utc),
            project="project/a",
        ),
        make_event(
            "event_2",
            datetime(2026, 9, 26, tzinfo=timezone.utc),
            project="project/b",
        ),
        make_event(
            "event_3",
            datetime(2026, 9, 27, tzinfo=timezone.utc),
            project="project/a",
        ),
    ]

    timeline = TimelineEngine().build(events)

    grouped = timeline.group_by_project()

    assert len(grouped["project/a"]) == 2
    assert len(grouped["project/b"]) == 1


def test_daily_summary():

    events = [
        make_event(
            "event_1",
            datetime(2026, 9, 25, 10, 0, tzinfo=timezone.utc),
            event_type=EventType.COMMIT,
        ),
        make_event(
            "event_2",
            datetime(2026, 9, 25, 12, 0, tzinfo=timezone.utc),
            event_type=EventType.ISSUE,
        ),
    ]

    evidence = [
        Evidence(
            id="evidence_1",
            evidence_type=EvidenceType.FACT,
            claim="Test fact",
            source_event_ids=["event_1"],
            confidence=0.9,
        )
    ]

    engine = TimelineEngine()

    timeline = engine.build(
        events,
        evidence,
    )

    summaries = engine.build_daily_summary(
        timeline
    )

    assert len(summaries) == 1

    summary = summaries[0]

    assert summary["date"] == "2026-09-25"
    assert summary["event_count"] == 2
    assert summary["event_types"]["commit"] == 1
    assert summary["event_types"]["issue"] == 1
    assert summary["evidence_ids"] == ["evidence_1"]


def test_get_recent():

    events = [
        make_event(
            f"event_{index}",
            datetime(
                2026,
                9,
                20 + index,
                tzinfo=timezone.utc,
            ),
        )
        for index in range(5)
    ]

    engine = TimelineEngine()

    timeline = engine.build(events)

    recent = engine.get_recent(
        timeline,
        limit=2,
    )

    assert [
        item.event_id
        for item in recent
    ] == [
        "event_3",
        "event_4",
    ]


def test_get_project_events():

    events = [
        make_event(
            "event_1",
            datetime(2026, 9, 25, tzinfo=timezone.utc),
            project="project/a",
        ),
        make_event(
            "event_2",
            datetime(2026, 9, 26, tzinfo=timezone.utc),
            project="project/b",
        ),
    ]

    engine = TimelineEngine()

    timeline = engine.build(events)

    project_events = engine.get_project_events(
        timeline,
        "project/a",
    )

    assert len(project_events) == 1
    assert project_events[0].event_id == "event_1"


def test_empty_timeline():

    timeline = TimelineEngine().build([])

    assert timeline.items == []

    assert timeline.group_by_date() == {}
    assert timeline.group_by_project() == {}
