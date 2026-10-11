from __future__ import annotations

from dataclasses import dataclass, field

from backend.processing.dependencies import DependencyGraph
from backend.processing.timeline import ProjectTimeline
from backend.schemas import (
    Evidence,
    EvidenceType,
    Event,
    EventType,
)


@dataclass
class ContextItem:
    """
    Represents one reconstructed piece of project context.
    """

    event_id: str
    title: str
    status: str
    description: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    dependency_ids: list[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "title": self.title,
            "status": self.status,
            "description": self.description,
            "evidence_ids": self.evidence_ids,
            "dependency_ids": self.dependency_ids,
            "confidence": self.confidence,
        }


@dataclass
class ProjectContext:
    """
    Reconstructed state of a project.
    """

    project: str
    summary: str

    current_state: str

    completed_work: list[ContextItem] = field(
        default_factory=list
    )

    active_work: list[ContextItem] = field(
        default_factory=list
    )

    blocked_work: list[ContextItem] = field(
        default_factory=list
    )

    planned_work: list[ContextItem] = field(
        default_factory=list
    )

    abandoned_work: list[ContextItem] = field(
        default_factory=list
    )

    unknown_work: list[ContextItem] = field(
        default_factory=list
    )

    important_decisions: list[Evidence] = field(
        default_factory=list
    )

    dependencies: list[dict] = field(
        default_factory=list
    )

    risks: list[str] = field(
        default_factory=list
    )

    evidence_ids: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict:
        return {
            "project": self.project,
            "summary": self.summary,
            "current_state": self.current_state,
            "completed_work": [
                item.to_dict()
                for item in self.completed_work
            ],
            "active_work": [
                item.to_dict()
                for item in self.active_work
            ],
            "blocked_work": [
                item.to_dict()
                for item in self.blocked_work
            ],
            "planned_work": [
                item.to_dict()
                for item in self.planned_work
            ],
            "abandoned_work": [
                item.to_dict()
                for item in self.abandoned_work
            ],
            "unknown_work": [
                item.to_dict()
                for item in self.unknown_work
            ],
            "important_decisions": [
                item.model_dump()
                for item in self.important_decisions
            ],
            "dependencies": self.dependencies,
            "risks": self.risks,
            "evidence_ids": self.evidence_ids,
        }


class ContextEngine:
    """
    Reconstructs the current project context from:

    - Events
    - Evidence
    - Timeline
    - Dependency graph

    This engine is deterministic.

    The LLM will later consume this structured context
    instead of trying to understand raw project data.
    """

    def build(
        self,
        events: list[Event],
        evidence: list[Evidence],
        timeline: ProjectTimeline,
        dependencies: DependencyGraph,
    ) -> ProjectContext:

        project = self._detect_project(events)

        event_by_id = {
            event.id: event
            for event in events
        }

        evidence_by_event = self._index_evidence(
            evidence
        )

        context_items = []

        for event in events:

            item = self._build_context_item(
                event=event,
                evidence=evidence_by_event.get(
                    event.id,
                    [],
                ),
                dependencies=dependencies,
            )

            context_items.append(item)

        completed_work = [
            item
            for item in context_items
            if item.status == "done"
        ]

        active_work = [
            item
            for item in context_items
            if item.status == "in_progress"
        ]

        blocked_work = [
            item
            for item in context_items
            if item.status == "blocked"
        ]

        planned_work = [
            item
            for item in context_items
            if item.status == "planned"
        ]

        abandoned_work = [
            item
            for item in context_items
            if item.status == "abandoned"
        ]

        unknown_work = [
            item
            for item in context_items
            if item.status == "unknown"
        ]

        important_decisions = [
            item
            for item in evidence
            if item.evidence_type
            == EvidenceType.DECISION
        ]

        dependency_dicts = dependencies.to_list()

        risks = self._detect_risks(
            blocked_work=blocked_work,
            dependencies=dependencies,
            event_by_id=event_by_id,
        )

        all_evidence_ids = self._collect_evidence_ids(
            evidence
        )

        current_state = self._determine_current_state(
            completed_work=completed_work,
            active_work=active_work,
            blocked_work=blocked_work,
            planned_work=planned_work,
        )

        summary = self._build_summary(
            project=project,
            events=events,
            completed=completed_work,
            active=active_work,
            blocked=blocked_work,
            planned=planned_work,
        )

        return ProjectContext(
            project=project,
            summary=summary,
            current_state=current_state,
            completed_work=completed_work,
            active_work=active_work,
            blocked_work=blocked_work,
            planned_work=planned_work,
            abandoned_work=abandoned_work,
            unknown_work=unknown_work,
            important_decisions=important_decisions,
            dependencies=dependency_dicts,
            risks=risks,
            evidence_ids=all_evidence_ids,
        )

    @staticmethod
    def _detect_project(
        events: list[Event],
    ) -> str:

        projects = [
            event.project
            for event in events
            if event.project
        ]

        if not projects:
            return "unknown"

        counts: dict[str, int] = {}

        for project in projects:
            counts[project] = (
                counts.get(project, 0) + 1
            )

        return max(
            counts,
            key=counts.get,
        )

    @staticmethod
    def _index_evidence(
        evidence: list[Evidence],
    ) -> dict[str, list[Evidence]]:

        index: dict[str, list[Evidence]] = {}

        for item in evidence:

            for event_id in item.source_event_ids:

                index.setdefault(
                    event_id,
                    [],
                ).append(item)

        return index

    def _build_context_item(
        self,
        event: Event,
        evidence: list[Evidence],
        dependencies: DependencyGraph,
    ) -> ContextItem:

        status = self._infer_status(
            event=event,
            evidence=evidence,
        )

        dependency_ids = []

        for dependency in dependencies.dependencies:

            if dependency.source_id == event.id:
                dependency_ids.append(
                    dependency.target_id
                )

        confidence = self._calculate_confidence(
            evidence
        )

        evidence_ids = [
            item.id
            for item in evidence
        ]

        title = (
            event.title
            or event.content[:120]
            or "Untitled work"
        )

        return ContextItem(
            event_id=event.id,
            title=title,
            status=status,
            description=event.content,
            evidence_ids=evidence_ids,
            dependency_ids=dependency_ids,
            confidence=confidence,
        )

    @staticmethod
    def _infer_status(
        event: Event,
        evidence: list[Evidence],
    ) -> str:

        text = (
            f"{event.title or ''} "
            f"{event.content or ''}"
        ).lower()

        metadata = event.metadata or {}

        # Explicit GitHub state.
        state = metadata.get("state")

        if (
            event.event_type == EventType.PULL_REQUEST
            and metadata.get("merged") is True
        ):
            return "done"

        if (
            event.event_type == EventType.ISSUE
            and state == "closed"
        ):
            return "done"

        # Evidence-based status.
        evidence_types = {
            item.evidence_type
            for item in evidence
        }

        if EvidenceType.STATUS_CHANGE in evidence_types:
            return "done"

        if EvidenceType.SOLUTION in evidence_types:
            return "done"

        if EvidenceType.DEPENDENCY in evidence_types:
            if any(
                keyword in text
                for keyword in [
                    "blocked",
                    "blocked by",
                    "cannot continue",
                    "can't continue",
                ]
            ):
                return "blocked"

        if any(
            keyword in text
            for keyword in [
                "blocked",
                "blocked by",
                "waiting for",
                "waiting on",
            ]
        ):
            return "blocked"

        if any(
            keyword in text
            for keyword in [
                "todo",
                "to do",
                "planned",
                "plan to",
                "will implement",
                "need to implement",
            ]
        ):
            return "planned"

        if any(
            keyword in text
            for keyword in [
                "implementing",
                "in progress",
                "working on",
                "currently working",
                "under development",
            ]
        ):
            return "in_progress"

        if event.event_type == EventType.COMMIT:
            return "done"

        return "unknown"

    @staticmethod
    def _calculate_confidence(
        evidence: list[Evidence],
    ) -> float:

        if not evidence:
            return 0.0

        return round(
            sum(
                item.confidence
                for item in evidence
            )
            / len(evidence),
            4,
        )

    @staticmethod
    def _collect_evidence_ids(
        evidence: list[Evidence],
    ) -> list[str]:

        result = []

        for item in evidence:

            if item.id not in result:
                result.append(item.id)

        return result

    @staticmethod
    def _determine_current_state(
        completed_work: list[ContextItem],
        active_work: list[ContextItem],
        blocked_work: list[ContextItem],
        planned_work: list[ContextItem],
    ) -> str:

        if blocked_work:
            return "blocked"

        if active_work:
            return "in_progress"

        if planned_work:
            return "planned"

        if completed_work:
            return "completed"

        return "unknown"

    @staticmethod
    def _build_summary(
        project: str,
        events: list[Event],
        completed: list[ContextItem],
        active: list[ContextItem],
        blocked: list[ContextItem],
        planned: list[ContextItem],
    ) -> str:

        return (
            f"Project {project} has "
            f"{len(events)} tracked events. "
            f"{len(completed)} items are completed, "
            f"{len(active)} are in progress, "
            f"{len(blocked)} are blocked, and "
            f"{len(planned)} are planned."
        )

    @staticmethod
    def _detect_risks(
        blocked_work: list[ContextItem],
        dependencies: DependencyGraph,
        event_by_id: dict[str, Event],
    ) -> list[str]:

        risks = []

        for item in blocked_work:

            risks.append(
                f"Blocked work: {item.title}"
            )

        for dependency in dependencies.dependencies:

            if dependency.target_id in event_by_id:

                target = event_by_id[
                    dependency.target_id
                ]

                if (
                    target.event_type
                    == EventType.ISSUE
                    and target.metadata.get("state")
                    == "open"
                ):
                    source = event_by_id.get(
                        dependency.source_id
                    )

                    source_title = (
                        source.title
                        if source
                        else dependency.source_id
                    )

                    risks.append(
                        f"{source_title} depends on "
                        f"an open issue: "
                        f"{target.title or target.id}"
                    )

        # Remove duplicates.
        unique = []

        for risk in risks:

            if risk not in unique:
                unique.append(risk)

        return unique