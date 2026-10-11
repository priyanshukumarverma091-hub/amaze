from datetime import datetime, timezone

from backend.schemas import Event, EventType

from backend.service import (
    ContextRecoveryService,
)


def make_commit(
    event_id: str,
    title: str,
    content: str,
    timestamp: datetime,
) -> Event:

    return Event(
        id=event_id,
        source="github",
        source_id=event_id,
        event_type=EventType.COMMIT,
        actor="alice",
        timestamp=timestamp,
        project="demo/project",
        title=title,
        content=content,
        url=f"https://github.com/demo/project/commit/{event_id}",
        references=[],
        metadata={},
    )


def test_analyze_events_end_to_end():

    events = [
        make_commit(
            event_id="commit_1",
            title="Initial implementation",
            content="Implemented backend API",
            timestamp=datetime(
                2026,
                1,
                1,
                tzinfo=timezone.utc,
            ),
        ),
        make_commit(
            event_id="commit_2",
            title="Fix API error",
            content="Fixed API error",
            timestamp=datetime(
                2026,
                1,
                2,
                tzinfo=timezone.utc,
            ),
        ),
    ]

    service = ContextRecoveryService()

    result = service.analyze_events(
        events,
        target_role="Backend Developer",
        previous_owner="alice",
    )

    assert len(result.raw_events) == 2

    assert len(
        result.normalized_events
    ) == 2

    assert len(
        result.events
    ) == 2

    assert len(
        result.evidence
    ) > 0

    assert result.timeline is not None

    assert result.dependencies is not None

    assert result.context is not None

    assert result.context.project == (
        "demo/project"
    )

    assert result.takeover_report is not None

    assert (
        result.takeover_report.project
        == "demo/project"
    )

    assert (
        result.takeover_report.target_role
        == "Backend Developer"
    )

    assert (
        result.takeover_report.previous_owner
        == "alice"
    )


def test_service_removes_duplicate_events():

    timestamp = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    event = make_commit(
        event_id="commit_duplicate",
        title="Same commit",
        content="Same content",
        timestamp=timestamp,
    )

    duplicate = make_commit(
        event_id="commit_duplicate",
        title="Same commit",
        content="Same content",
        timestamp=timestamp,
    )

    service = ContextRecoveryService()

    result = service.analyze_events(
        [
            event,
            duplicate,
        ]
    )

    assert len(
        result.raw_events
    ) == 2

    assert len(
        result.normalized_events
    ) == 2

    assert len(
        result.events
    ) == 1


def test_service_confidence_is_generated():

    event = make_commit(
        event_id="commit_confidence",
        title="Implemented feature",
        content="Implemented feature successfully",
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    service = ContextRecoveryService()

    result = service.analyze_events(
        [event]
    )

    assert result.confidence

    for key, value in result.confidence.items():

        assert isinstance(key, str)

        assert 0.0 <= value.score <= 1.0

        assert value.level in {
            "very_low",
            "low",
            "medium",
            "high",
            "very_high",
        }


def test_service_to_dict_is_json_safe():

    event = make_commit(
        event_id="commit_json",
        title="JSON test",
        content="Completed JSON test",
        timestamp=datetime(
            2026,
            1,
            1,
            tzinfo=timezone.utc,
        ),
    )

    service = ContextRecoveryService()

    result = service.analyze_events(
        [event]
    )

    data = result.to_dict()

    assert isinstance(
        data,
        dict,
    )

    assert data["event_count"] == 1

    assert data["evidence_count"] >= 1

    assert isinstance(
        data["events"],
        list,
    )

    assert isinstance(
        data["evidence"],
        list,
    )

    assert isinstance(
        data["timeline"],
        list,
    )

    assert isinstance(
        data["dependencies"],
        list,
    )

    assert isinstance(
        data["context"],
        dict,
    )

    assert isinstance(
        data["decisions"],
        list,
    )

    assert isinstance(
        data["conflicts"],
        list,
    )

    assert isinstance(
        data["confidence"],
        dict,
    )

    assert isinstance(
        data["takeover_report"],
        dict,
    )


def test_github_service_requires_connector():

    service = ContextRecoveryService()

    try:
        service.analyze_github_repository(
            "demo/project"
        )
    except RuntimeError as exc:
        assert (
            "GitHub connector is not configured"
            in str(exc)
        )
    else:
        raise AssertionError(
            "Expected RuntimeError"
        )