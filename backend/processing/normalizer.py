from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from backend.schemas import Event


class EventNormalizer:
    """
    Normalizes events from different sources into a consistent format.

    Current supported source:
    - GitHub

    Future sources:
    - Slack
    - Discord
    - Notion
    - Google Drive
    """

    def normalize(self, event: Event) -> Event:
        """
        Return a normalized copy of an Event.
        """

        normalized = deepcopy(event)

        normalized.source = self._normalize_source(
            normalized.source
        )

        normalized.source_id = self._normalize_text(
            normalized.source_id
        )

        normalized.actor = self._normalize_actor(
            normalized.actor
        )

        normalized.project = self._normalize_project(
            normalized.project
        )

        normalized.title = self._normalize_title(
            normalized.title
        )

        normalized.content = self._normalize_content(
            normalized.content
        )

        normalized.url = self._normalize_url(
            normalized.url
        )

        normalized.references = self._normalize_references(
            normalized.references
        )

        normalized.metadata = self._normalize_metadata(
            normalized.metadata
        )

        normalized.timestamp = self._normalize_timestamp(
            normalized.timestamp
        )

        return normalized

    def normalize_many(
        self,
        events: list[Event],
    ) -> list[Event]:
        """
        Normalize multiple events while preserving order.
        """

        return [
            self.normalize(event)
            for event in events
        ]

    @staticmethod
    def _normalize_text(
        value: str | None,
    ) -> str | None:

        if value is None:
            return None

        value = str(value).strip()

        return value if value else None

    @classmethod
    def _normalize_source(
        cls,
        source: str,
    ) -> str:

        source = cls._normalize_text(source)

        if source is None:
            return "unknown"

        return source.lower()

    @classmethod
    def _normalize_actor(
        cls,
        actor: str | None,
    ) -> str | None:

        actor = cls._normalize_text(actor)

        if actor is None:
            return None

        return actor.lower()

    @classmethod
    def _normalize_project(
        cls,
        project: str | None,
    ) -> str | None:

        project = cls._normalize_text(project)

        if project is None:
            return None

        return project.strip()

    @classmethod
    def _normalize_title(
        cls,
        title: str | None,
    ) -> str | None:

        title = cls._normalize_text(title)

        if title is None:
            return None

        # Collapse repeated whitespace.
        return " ".join(title.split())

    @staticmethod
    def _normalize_content(
        content: str,
    ) -> str:

        if not content:
            return ""

        # Normalize line endings.
        content = content.replace("\r\n", "\n")
        content = content.replace("\r", "\n")

        # Remove trailing whitespace from every line.
        lines = [
            line.rstrip()
            for line in content.split("\n")
        ]

        # Remove excessive blank lines.
        normalized_lines = []
        previous_blank = False

        for line in lines:
            is_blank = not line.strip()

            if is_blank and previous_blank:
                continue

            normalized_lines.append(line)

            previous_blank = is_blank

        return "\n".join(normalized_lines).strip()

    @staticmethod
    def _normalize_url(
        url: str | None,
    ) -> str | None:

        if url is None:
            return None

        url = str(url).strip()

        return url if url else None

    @classmethod
    def _normalize_references(
        cls,
        references: list[str],
    ) -> list[str]:

        normalized = []

        for reference in references:
            value = cls._normalize_text(reference)

            if value and value not in normalized:
                normalized.append(value)

        return normalized

    @classmethod
    def _normalize_metadata(
        cls,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:

        if not metadata:
            return {}

        normalized = {}

        for key, value in metadata.items():
            normalized_key = cls._normalize_text(str(key))

            if normalized_key is None:
                continue

            normalized[normalized_key] = value

        return normalized

    @staticmethod
    def _normalize_timestamp(
        timestamp: datetime,
    ) -> datetime:

        if timestamp.tzinfo is None:
            return timestamp.replace(
                tzinfo=timezone.utc
            )

        return timestamp.astimezone(timezone.utc)