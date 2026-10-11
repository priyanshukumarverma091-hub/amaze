from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.schemas import Event, Evidence, EvidenceType


@dataclass
class Dependency:
    """
    Represents a relationship where one project item depends on another.
    """

    source_id: str
    target_id: str
    dependency_type: str
    reason: str
    confidence: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "dependency_type": self.dependency_type,
            "reason": self.reason,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids,
        }


class DependencyGraph:
    """
    Collection of project dependencies.
    """

    def __init__(self, dependencies: list[Dependency] | None = None):
        self.dependencies = dependencies or []

    def to_list(self) -> list[dict]:
        return [
            dependency.to_dict()
            for dependency in self.dependencies
        ]

    def get_dependencies_of(
        self,
        event_id: str,
    ) -> list[Dependency]:

        return [
            dependency
            for dependency in self.dependencies
            if dependency.source_id == event_id
        ]

    def get_dependents_of(
        self,
        event_id: str,
    ) -> list[Dependency]:

        return [
            dependency
            for dependency in self.dependencies
            if dependency.target_id == event_id
        ]


class DependencyEngine:
    """
    Builds a conservative dependency graph from project events
    and extracted evidence.

    This version uses explicit references and dependency language.
    It intentionally avoids guessing semantic relationships.
    """

    def build(
        self,
        events: list[Event],
        evidence: list[Evidence] | None = None,
    ) -> DependencyGraph:

        evidence = evidence or []

        event_by_id = {
            event.id: event
            for event in events
        }

        dependencies: list[Dependency] = []

        # ---------------------------------------------------------
        # 1. Explicit event references
        # ---------------------------------------------------------

        for event in events:
            for reference in event.references:

                target_id = self._resolve_reference(
                    reference,
                    event_by_id,
                )

                if target_id is None:
                    continue

                if target_id == event.id:
                    continue

                dependencies.append(
                    Dependency(
                        source_id=event.id,
                        target_id=target_id,
                        dependency_type="references",
                        reason=(
                            f"Event explicitly references "
                            f"{target_id}."
                        ),
                        confidence=0.95,
                        evidence_ids=[],
                    )
                )

        # ---------------------------------------------------------
        # 2. Evidence-based dependencies
        # ---------------------------------------------------------

        for item in evidence:

            if item.evidence_type != EvidenceType.DEPENDENCY:
                continue

            source_event_ids = item.source_event_ids

            if not source_event_ids:
                continue

            source_id = source_event_ids[0]

            target_id = self._extract_target_from_text(
                item.description or item.claim,
                event_by_id,
                source_id,
            )

            if target_id is None:
                continue

            dependencies.append(
                Dependency(
                    source_id=source_id,
                    target_id=target_id,
                    dependency_type="evidence_dependency",
                    reason=item.claim,
                    confidence=item.confidence,
                    evidence_ids=[item.id],
                )
            )

        # ---------------------------------------------------------
        # 3. Remove duplicate relationships
        # ---------------------------------------------------------

        dependencies = self._deduplicate(
            dependencies
        )

        return DependencyGraph(dependencies)

    @staticmethod
    def _resolve_reference(
        reference: str,
        event_by_id: dict[str, Event],
    ) -> str | None:

        reference = reference.strip()

        # Direct event ID.
        if reference in event_by_id:
            return reference

        # GitHub-style references:
        # issue:123
        match = re.fullmatch(
            r"issue:(\d+)",
            reference.lower(),
        )

        if match:
            issue_number = match.group(1)

            for event in event_by_id.values():

                if event.event_type.value != "issue":
                    continue

                number = event.metadata.get("number")

                if str(number) == issue_number:
                    return event.id

        return None

    @staticmethod
    def _extract_target_from_text(
        text: str,
        event_by_id: dict[str, Event],
        source_id: str,
    ) -> str | None:

        if not text:
            return None

        lowered = text.lower()

        dependency_patterns = [
            r"depends on\s+([a-zA-Z0-9_-]+)",
            r"blocked by\s+([a-zA-Z0-9_-]+)",
            r"requires\s+([a-zA-Z0-9_-]+)",
            r"required by\s+([a-zA-Z0-9_-]+)",
        ]

        for pattern in dependency_patterns:

            match = re.search(
                pattern,
                lowered,
            )

            if not match:
                continue

            candidate = match.group(1)

            for event_id in event_by_id:

                if event_id == source_id:
                    continue

                if event_id.lower() == candidate:
                    return event_id

        return None

    @staticmethod
    def _deduplicate(
        dependencies: list[Dependency],
    ) -> list[Dependency]:

        unique: list[Dependency] = []
        seen: set[tuple[str, str, str]] = set()

        for dependency in dependencies:

            key = (
                dependency.source_id,
                dependency.target_id,
                dependency.dependency_type,
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(dependency)

        return unique