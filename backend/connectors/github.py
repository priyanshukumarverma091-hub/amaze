from datetime import datetime, timezone
from typing import Optional

from github import Auth, Github
from github.GithubException import GithubException

from backend.schemas import Event, EventType


class GitHubConnector:
    """
    Read-only connector for collecting GitHub repository activity.

    Collects:
    - Commits
    - Pull Requests
    - Issues

    All GitHub objects are converted into our common Event schema.
    """

    def __init__(self, token: str):
        if not token:
            raise ValueError("GitHub token is required.")

        self.client = Github(auth=Auth.Token(token))

    def _datetime(self, value: Optional[datetime]) -> datetime:
        """
        Make sure timestamps are timezone-aware.
        """

        if value is None:
            return datetime.now(timezone.utc)

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value

    def get_repository(self, repository: str):
        """
        Load a GitHub repository.

        repository format:
            owner/repository
        """

        try:
            return self.client.get_repo(repository)

        except GithubException as exc:
            raise RuntimeError(
                f"Could not access GitHub repository '{repository}': "
                f"{exc.data if hasattr(exc, 'data') else exc}"
            ) from exc

    def get_commits(
        self,
        repository: str,
        limit: int = 100
    ) -> list[Event]:

        repo = self.get_repository(repository)

        events = []

        commits = repo.get_commits()

        for index, commit in enumerate(commits):

            if index >= limit:
                break

            commit_data = commit.commit

            author = None

            if commit.author:
                author = commit.author.login

            commit_author = commit_data.author

            timestamp = None

            if commit_author:
                timestamp = commit_author.date

            timestamp = self._datetime(timestamp)

            message = commit_data.message or ""

            event = Event(
                id=f"github_commit_{commit.sha}",
                source="github",
                source_id=commit.sha,
                event_type=EventType.COMMIT,
                actor=author,
                timestamp=timestamp,
                project=repo.full_name,
                title=message.split("\n")[0][:200],
                content=message,
                url=commit.html_url,
                references=[],
                metadata={
                    "sha": commit.sha,
                    "repository": repo.full_name,
                    "author_name": (
                        commit_author.name
                        if commit_author
                        else None
                    ),
                },
            )

            events.append(event)

        return events

    def get_pull_requests(
        self,
        repository: str,
        limit: int = 100
    ) -> list[Event]:

        repo = self.get_repository(repository)

        events = []

        pull_requests = repo.get_pulls(
            state="all",
            sort="updated",
            direction="desc",
        )

        for index, pr in enumerate(pull_requests):

            if index >= limit:
                break

            actor = pr.user.login if pr.user else None

            timestamp = self._datetime(
                pr.updated_at or pr.created_at
            )

            content_parts = []

            if pr.body:
                content_parts.append(pr.body)

            if pr.head:
                content_parts.append(
                    f"Head branch: {pr.head.ref}"
                )

            if pr.base:
                content_parts.append(
                    f"Base branch: {pr.base.ref}"
                )

            content = "\n\n".join(content_parts)

            event = Event(
                id=f"github_pr_{pr.number}",
                source="github",
                source_id=str(pr.number),
                event_type=EventType.PULL_REQUEST,
                actor=actor,
                timestamp=timestamp,
                project=repo.full_name,
                title=pr.title,
                content=content,
                url=pr.html_url,
                references=[
                    f"issue:{pr.number}"
                ],
                metadata={
                    "number": pr.number,
                    "state": pr.state,
                    "merged": pr.merged,
                    "draft": pr.draft,
                    "repository": repo.full_name,
                    "head_branch": (
                        pr.head.ref
                        if pr.head
                        else None
                    ),
                    "base_branch": (
                        pr.base.ref
                        if pr.base
                        else None
                    ),
                },
            )

            events.append(event)

        return events

    def get_issues(
        self,
        repository: str,
        limit: int = 100
    ) -> list[Event]:

        repo = self.get_repository(repository)

        events = []

        issues = repo.get_issues(
            state="all",
            sort="updated",
            direction="desc",
        )

        for index, issue in enumerate(issues):

            if index >= limit:
                break

            # GitHub's Issues API also returns pull requests.
            # We don't want to duplicate them here.
            if issue.pull_request is not None:
                continue

            actor = issue.user.login if issue.user else None

            timestamp = self._datetime(
                issue.updated_at or issue.created_at
            )

            content = issue.body or ""

            labels = [
                label.name
                for label in issue.labels
            ]

            event = Event(
                id=f"github_issue_{issue.number}",
                source="github",
                source_id=str(issue.number),
                event_type=EventType.ISSUE,
                actor=actor,
                timestamp=timestamp,
                project=repo.full_name,
                title=issue.title,
                content=content,
                url=issue.html_url,
                references=[
                    f"issue:{issue.number}"
                ],
                metadata={
                    "number": issue.number,
                    "state": issue.state,
                    "labels": labels,
                    "repository": repo.full_name,
                },
            )

            events.append(event)

        return events

    def collect_all(
        self,
        repository: str,
        commit_limit: int = 100,
        pr_limit: int = 100,
        issue_limit: int = 100,
    ) -> list[Event]:

        events = []

        events.extend(
            self.get_commits(
                repository,
                limit=commit_limit,
            )
        )

        events.extend(
            self.get_pull_requests(
                repository,
                limit=pr_limit,
            )
        )

        events.extend(
            self.get_issues(
                repository,
                limit=issue_limit,
            )
        )

        # Sort newest first
        events.sort(
            key=lambda event: event.timestamp,
            reverse=True,
        )

        return events