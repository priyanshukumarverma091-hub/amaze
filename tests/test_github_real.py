import os

from dotenv import load_dotenv

from backend.connectors import GitHubConnector


load_dotenv()


def test_retro_ai_collection():
    token = os.getenv("GITHUB_TOKEN")

    assert token, "GITHUB_TOKEN is not loaded."

    connector = GitHubConnector(token)

    events = connector.collect_all(
        "priyanshukumarverma091-hub/RETRO-AI",
        commit_limit=10,
        pr_limit=10,
        issue_limit=10,
    )

    assert isinstance(events, list)
    assert len(events) > 0

    print("\n===== GITHUB EVENTS =====")

    for event in events:
        print(
            f"\n[{event.event_type.value.upper()}]"
            f"\nID: {event.id}"
            f"\nActor: {event.actor}"
            f"\nTitle: {event.title}"
            f"\nTime: {event.timestamp}"
            f"\nURL: {event.url}"
        )