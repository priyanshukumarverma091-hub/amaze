from datetime import datetime, timezone

from backend.processing import EventDeduplicator
from backend.schemas import Event, EventType


def make_event(
    event_id: str,
    source_id: str,
    url: str,
    title: str,
    content: str,
) -> Event:

    return Event(
        id=event_id,
        source="github",
        source_id=source_id,
        event_type=EventType.COMMIT,
        actor="priyanshu",
        timestamp=datetime(
            2026,
            10,
            1,
            12,
            0,
            tzinfo=timezone.utc,
        ),
        project="test/project",
        title=title,
        content=content,
        url=url,
    )


def test_exact_duplicate_is_removed():

    event = make_event(
        "event_1",
        "commit_1",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README file",
    )

    events = [
        event,
        event.model_copy(),
    ]

    deduplicator = EventDeduplicator()

    result = deduplicator.deduplicate(events)

    assert len(result) == 1
    assert result[0].id == "event_1"


def test_duplicate_source_id_is_removed():

    event_1 = make_event(
        "event_1",
        "commit_123",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README",
    )

    event_2 = make_event(
        "event_2",
        "commit_123",
        "https://github.com/test/commit/2",
        "Something else",
        "Something else",
    )

    deduplicator = EventDeduplicator()

    result = deduplicator.deduplicate(
        [event_1, event_2]
    )

    assert len(result) == 1
    assert result[0].id == "event_1"


def test_duplicate_url_is_removed():

    event_1 = make_event(
        "event_1",
        "commit_1",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README",
    )

    event_2 = make_event(
        "event_2",
        "commit_2",
        "https://github.com/test/commit/1",
        "Different title",
        "Different content",
    )

    deduplicator = EventDeduplicator()

    result = deduplicator.deduplicate(
        [event_1, event_2]
    )

    assert len(result) == 1


def test_unique_events_are_preserved():

    event_1 = make_event(
        "event_1",
        "commit_1",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README",
    )

    event_2 = make_event(
        "event_2",
        "commit_2",
        "https://github.com/test/commit/2",
        "Update app",
        "Updated app",
    )

    deduplicator = EventDeduplicator()

    result = deduplicator.deduplicate(
        [event_1, event_2]
    )

    assert len(result) == 2


def test_find_duplicates():

    event_1 = make_event(
        "event_1",
        "commit_1",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README",
    )

    event_2 = event_1.model_copy(
        update={"id": "event_2"}
    )

    deduplicator = EventDeduplicator()

    duplicates = deduplicator.find_duplicates(
        [event_1, event_2]
    )

    assert len(duplicates) == 1
    assert duplicates[0].id == "event_2"


def test_deduplicate_many():

    event_1 = make_event(
        "event_1",
        "commit_1",
        "https://github.com/test/commit/1",
        "Update README",
        "Updated README",
    )

    event_2 = make_event(
        "event_2",
        "commit_2",
        "https://github.com/test/commit/2",
        "Update app",
        "Updated app",
    )

    event_1_duplicate = event_1.model_copy(
        update={"id": "event_3"}
    )

    deduplicator = EventDeduplicator()

    result = deduplicator.deduplicate_many(
        [
            [event_1],
            [event_2],
            [event_1_duplicate],
        ]
    )

    assert len(result) == 2