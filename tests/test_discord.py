from datetime import datetime, timezone

from backend.connectors.discord import DiscordConnector
from backend.schemas import EventType


def make_connector():
    return DiscordConnector("test-token")


def test_message_to_event():

    connector = make_connector()

    message = {
        "id": "123456789",
        "content": "We fixed the authentication bug.",
        "timestamp": "2026-10-01T12:30:00.000Z",
        "guild_id": "guild123",
        "channel_id": "channel456",
        "author": {
            "id": "user123",
            "username": "alice",
            "global_name": "Alice",
        },
        "attachments": [],
        "mentions": [],
        "message_reference": None,
        "pinned": False,
        "type": 0,
    }

    event = connector.message_to_event(
        message,
        project="demo/project",
        channel_name="backend",
    )

    assert event.id == "discord_message_123456789"
    assert event.source == "discord"
    assert event.source_id == "123456789"
    assert event.event_type == EventType.MESSAGE
    assert event.actor == "Alice"
    assert event.project == "demo/project"
    assert event.content == "We fixed the authentication bug."
    assert event.title == "We fixed the authentication bug."
    assert event.metadata["channel_name"] == "backend"
    assert event.metadata["author_id"] == "user123"


def test_message_to_event_with_reply():

    connector = make_connector()

    message = {
        "id": "200",
        "content": "Yes, this decision works.",
        "timestamp": "2026-10-01T13:00:00Z",
        "guild_id": "guild1",
        "channel_id": "channel1",
        "author": {
            "id": "user1",
            "username": "bob",
        },
        "mentions": [],
        "message_reference": {
            "message_id": "100",
        },
    }

    event = connector.message_to_event(message)

    assert "discord_message:100" in event.references


def test_empty_message_gets_fallback_title():

    connector = make_connector()

    message = {
        "id": "300",
        "content": "",
        "timestamp": "2026-10-01T13:00:00Z",
        "channel_id": "channel1",
        "author": {
            "id": "user1",
            "username": "bob",
        },
    }

    event = connector.message_to_event(
        message,
        channel_name="general",
    )

    assert event.title == "Message in #general"


def test_connector_requires_token():

    try:
        DiscordConnector("")
    except ValueError as exc:
        assert "Discord bot token is required" in str(exc)
    else:
        raise AssertionError(
            "Expected ValueError"
        )


def test_timestamp_is_timezone_aware():

    connector = make_connector()

    message = {
        "id": "400",
        "content": "Test",
        "timestamp": "2026-10-01T13:00:00Z",
        "channel_id": "channel1",
        "author": {
            "id": "user1",
            "username": "bob",
        },
    }

    event = connector.message_to_event(message)

    assert event.timestamp.tzinfo is not None
    assert event.timestamp.tzinfo.utcoffset(
        event.timestamp
    ) is not None