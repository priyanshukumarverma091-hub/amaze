from __future__ import annotations

import hashlib
import re
from collections import defaultdict

from backend.schemas import Event


class EventDeduplicator:
    """
    Removes duplicate events while preserving the original event order.

    Deduplication levels:

    1. Exact event ID
    2. Same source + source ID
    3. Same URL
    4. Exact content fingerprint

    The deduplicator is intentionally conservative.
    It does NOT perform fuzzy or semantic matching.
    """

    def deduplicate(
        self,
        events: list[Event],
    ) -> list[Event]:
        """
        Remove duplicate events from a list.

        The first occurrence of an event is preserved.
        """

        unique_events: list[Event] = []

        seen_ids: set[str] = set()
        seen_source_ids: set[str] = set()
        seen_urls: set[str] = set()
        seen_fingerprints: set[str] = set()

        for event in events:

            # --------------------------------------------------
            # 1. Exact Event ID
            # --------------------------------------------------
            event_id = self._normalize_value(event.id)

            if event_id and event_id in seen_ids:
                continue

            # --------------------------------------------------
            # 2. Source + Source ID
            # --------------------------------------------------
            source_key = self._build_source_key(event)

            if source_key and source_key in seen_source_ids:
                continue

            # --------------------------------------------------
            # 3. URL
            # --------------------------------------------------
            url = self._normalize_url(event.url)

            if url and url in seen_urls:
                continue

            # --------------------------------------------------
            # 4. Content fingerprint
            # --------------------------------------------------
            fingerprint = self._content_fingerprint(event)

            if fingerprint in seen_fingerprints:
                continue

            # --------------------------------------------------
            # Event is unique
            # --------------------------------------------------
            unique_events.append(event)

            if event_id:
                seen_ids.add(event_id)

            if source_key:
                seen_source_ids.add(source_key)

            if url:
                seen_urls.add(url)

            seen_fingerprints.add(fingerprint)

        return unique_events

    def find_duplicates(
        self,
        events: list[Event],
    ) -> list[Event]:
        """
        Return only the events that would be removed
        by deduplication.
        """

        duplicates: list[Event] = []

        seen_ids: set[str] = set()
        seen_source_ids: set[str] = set()
        seen_urls: set[str] = set()
        seen_fingerprints: set[str] = set()

        for event in events:

            event_id = self._normalize_value(event.id)
            source_key = self._build_source_key(event)
            url = self._normalize_url(event.url)
            fingerprint = self._content_fingerprint(event)

            is_duplicate = False

            if event_id and event_id in seen_ids:
                is_duplicate = True

            elif source_key and source_key in seen_source_ids:
                is_duplicate = True

            elif url and url in seen_urls:
                is_duplicate = True

            elif fingerprint in seen_fingerprints:
                is_duplicate = True

            if is_duplicate:
                duplicates.append(event)
                continue

            if event_id:
                seen_ids.add(event_id)

            if source_key:
                seen_source_ids.add(source_key)

            if url:
                seen_urls.add(url)

            seen_fingerprints.add(fingerprint)

        return duplicates

    def deduplicate_many(
        self,
        event_groups: list[list[Event]],
    ) -> list[Event]:
        """
        Flatten multiple event groups and deduplicate them.

        Useful later when events come from:

        GitHub + Slack + Discord + Docs
        """

        flattened: list[Event] = []

        for group in event_groups:
            flattened.extend(group)

        return self.deduplicate(flattened)

    @staticmethod
    def _normalize_value(
        value: str | None,
    ) -> str:

        if value is None:
            return ""

        return str(value).strip().lower()

    def _build_source_key(
        self,
        event: Event,
    ) -> str:

        source = self._normalize_value(event.source)
        source_id = self._normalize_value(event.source_id)

        if not source or not source_id:
            return ""

        return f"{source}:{source_id}"

    @classmethod
    def _normalize_url(
        cls,
        url: str | None,
    ) -> str:

        if not url:
            return ""

        normalized = url.strip().lower()

        # Remove trailing slash.
        normalized = normalized.rstrip("/")

        # Remove URL fragments.
        normalized = normalized.split("#", 1)[0]

        return normalized

    @classmethod
    def _normalize_content(
        cls,
        content: str | None,
    ) -> str:

        if not content:
            return ""

        content = content.lower()

        # Normalize whitespace.
        content = re.sub(
            r"\s+",
            " ",
            content,
        )

        return content.strip()

    @classmethod
    def _normalize_title(
        cls,
        title: str | None,
    ) -> str:

        if not title:
            return ""

        title = title.lower()

        title = re.sub(
            r"\s+",
            " ",
            title,
        )

        return title.strip()

    def _content_fingerprint(
        self,
        event: Event,
    ) -> str:

        source = self._normalize_value(event.source)

        event_type = event.event_type.value

        actor = self._normalize_value(
            event.actor
        )

        title = self._normalize_title(
            event.title
        )

        content = self._normalize_content(
            event.content
        )

        timestamp = event.timestamp.isoformat()

        raw = "|".join(
            [
                source,
                event_type,
                actor,
                title,
                content,
                timestamp,
            ]
        )

        return hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()