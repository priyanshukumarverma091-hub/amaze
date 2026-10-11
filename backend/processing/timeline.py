from __future__ import annotations

from collections import defaultdict
from datetime import datetime

from backend.schemas import Event, Evidence


class TimelineItem:
    """
    Represents one point in the reconstructed project timeline.
    """

    def __init__(
        self,
        event_id: str,
        timestamp: datetime,
        event_type: str,
        title: str | None,
        actor: str | None,
        project: str | None,
        source: str,
        url: str | None,
        evidence_ids: list[str] | None = None,
    ):
        self.event_id = event_id
        self.timestamp = timestamp
        self.event_type = event_type
        self.title = title
        self.actor = actor
        self.project = project
        self.source = source
        self.url = url
        self.evidence_ids = evidence_ids or []

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "title": self.title,
            "actor": self.actor,
            "project": self.project,
            "source": self.source,
            "url": self.url,
            "evidence_ids": self.evidence_ids,
        }


class ProjectTimeline:
    """
    Reconstructs project history from events and extracted evidence.

    Responsibilities:
    - Sort events chronologically
    - Connect evidence to source events
    - Group events by date
    - Group events by project
    - Preserve source traceability
    """

    def __init__(
        self,
        items: list[TimelineItem],
    ):
        self.items = items

    def to_list(self) -> list[dict]:
        return [item.to_dict() for item in self.items]

    def group_by_date(self) -> dict[str, list[TimelineItem]]:
        grouped: dict[str, list[TimelineItem]] = defaultdict(list)

        for item in self.items:
            date_key = item.timestamp.date().isoformat()
            grouped[date_key].append(item)

        return dict(grouped)

    def group_by_project(self) -> dict[str, list[TimelineItem]]:
        grouped: dict[str, list[TimelineItem]] = defaultdict(list)

        for item in self.items:
            project = item.project or "unknown"
            grouped[project].append(item)

        return dict(grouped)


class TimelineEngine:
    """
    Builds a chronological project timeline from normalized events.

    Evidence is linked back to the original event IDs so every
    timeline item remains traceable to its source.
    """

    def build(
        self,
        events: list[Event],
        evidence: list[Evidence] | None = None,
    ) -> ProjectTimeline:

        evidence = evidence or []

        evidence_by_event = self._index_evidence(evidence)

        sorted_events = sorted(
            events,
            key=lambda event: event.timestamp,
        )

        items = []

        for event in sorted_events:
            event_evidence = evidence_by_event.get(
                event.id,
                [],
            )

            evidence_ids = [
                item.id
                for item in event_evidence
            ]

            item = TimelineItem(
                event_id=event.id,
                timestamp=event.timestamp,
                event_type=event.event_type.value,
                title=event.title,
                actor=event.actor,
                project=event.project,
                source=event.source,
                url=event.url,
                evidence_ids=evidence_ids,
            )

            items.append(item)

        return ProjectTimeline(items)

    @staticmethod
    def _index_evidence(
        evidence: list[Evidence],
    ) -> dict[str, list[Evidence]]:

        index: dict[str, list[Evidence]] = defaultdict(list)

        for item in evidence:
            for event_id in item.source_event_ids:
                index[event_id].append(item)

        return dict(index)

    def build_daily_summary(
        self,
        timeline: ProjectTimeline,
    ) -> list[dict]:

        grouped = timeline.group_by_date()

        summaries = []

        for date, items in sorted(grouped.items()):

            event_types = defaultdict(int)
            actors = set()

            for item in items:
                event_types[item.event_type] += 1

                if item.actor:
                    actors.add(item.actor)

            summaries.append(
                {
                    "date": date,
                    "event_count": len(items),
                    "event_types": dict(event_types),
                    "actors": sorted(actors),
                    "event_ids": [
                        item.event_id
                        for item in items
                    ],
                    "evidence_ids": [
                        evidence_id
                        for item in items
                        for evidence_id in item.evidence_ids
                    ],
                }
            )

        return summaries

    def get_recent(
        self,
        timeline: ProjectTimeline,
        limit: int = 10,
    ) -> list[TimelineItem]:

        if limit <= 0:
            return []

        return timeline.items[-limit:]

    def get_project_events(
        self,
        timeline: ProjectTimeline,
        project: str,
    ) -> list[TimelineItem]:

        return [
            item
            for item in timeline.items
            if item.project == project
        ]