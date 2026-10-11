from datetime import datetime

from backend.processing import EventNormalizer
from backend.schemas import Event, EventType


def create_sample_event() -> Event:
    return Event(
        id="test_001",
        source="GitHub",
        source_id=" abc123 ",
        event_type=EventType.COMMIT,
        actor=" Priyanshu ",
        timestamp=datetime(
            2026,
            10,
            1,
            12,
            0,
        ),
        project=" priyanshu/test-project ",
        title="  Update   README.md  ",
        content=(
            "First line\r\n"
            "Second line\r\n"
            "\r\n"
            "\r\n"
            "Third line   "
        ),
        url=" https://github.com/test ",
        references=[
            "issue:42",
            "issue:42",
            " pr:10 ",
        ],
        metadata={
            " Repository ": "test/repo",
            "number": 10,
        },
    )


def test_event_normalization():

    normalizer = EventNormalizer()

    event = create_sample_event()

    normalized = normalizer.normalize(event)

    assert normalized.source == "github"

    assert normalized.source_id == "abc123"

    assert normalized.actor == "priyanshu"

    assert normalized.project == "priyanshu/test-project"

    assert normalized.title == "Update README.md"

    assert normalized.content == (
        "First line\n"
        "Second line\n"
        "\n"
        "Third line"
    )

    assert normalized.url == "https://github.com/test"

    assert normalized.references == [
        "issue:42",
        "pr:10",
    ]

    assert normalized.metadata == {
        "Repository": "test/repo",
        "number": 10,
    }


def test_normalization_preserves_event_id():

    normalizer = EventNormalizer()

    event = create_sample_event()

    normalized = normalizer.normalize(event)

    assert normalized.id == event.id


def test_normalization_preserves_event_type():

    normalizer = EventNormalizer()

    event = create_sample_event()

    normalized = normalizer.normalize(event)

    assert normalized.event_type == EventType.COMMIT


def test_normalize_many():

    normalizer = EventNormalizer()

    events = [
        create_sample_event(),
        create_sample_event(),
    ]

    normalized_events = normalizer.normalize_many(events)

    assert len(normalized_events) == 2

    assert all(
        event.source == "github"
        for event in normalized_events
    )