import os

import pytest

from backend.connectors import GitHubConnector


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not configured",
)
def test_github_repository_access():

    connector = GitHubConnector(
        os.environ["GITHUB_TOKEN"]
    )

    repo = connector.get_repository(
        "octocat/Hello-World"
    )

    assert repo.full_name == "octocat/Hello-World"


@pytest.mark.skipif(
    not os.getenv("GITHUB_TOKEN"),
    reason="GITHUB_TOKEN not configured",
)
def test_github_commit_collection():

    connector = GitHubConnector(
        os.environ["GITHUB_TOKEN"]
    )

    events = connector.get_commits(
        "octocat/Hello-World",
        limit=5,
    )

    assert isinstance(events, list)

    for event in events:
        assert event.source == "github"
        assert event.event_type.value == "commit"
        assert event.source_id
        assert event.content