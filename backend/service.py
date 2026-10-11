from __future__ import annotations

import os
from dataclasses import dataclass, field

from backend.connectors.github import GitHubConnector
from backend.processing.deduplicator import EventDeduplicator
from backend.processing.dependencies import (
    DependencyEngine,
    DependencyGraph,
)
from backend.processing.evidence import EvidenceExtractor
from backend.processing.normalizer import EventNormalizer
from backend.processing.timeline import (
    ProjectTimeline,
    TimelineEngine,
)
from backend.reasoning.confidence import (
    ConfidenceEngine,
    ConfidenceResult,
)
from backend.reasoning.conflict_detector import (
    Conflict,
    ConflictDetector,
)
from backend.reasoning.context_engine import (
    ContextEngine,
    ProjectContext,
)
from backend.reasoning.decision_engine import (
    DecisionEngine,
)
from backend.reasoning.takeover_engine import (
    TakeoverEngine,
)
from backend.schemas import (
    Decision,
    Evidence,
    Event,
    TakeoverReport,
)


@dataclass
class ServiceResult:
    """
    Complete output of the Context Recovery Engine.

    This object contains every intermediate layer so the
    frontend/n8n workflow can inspect the reasoning chain
    instead of receiving only the final report.
    """

    raw_events: list[Event] = field(
        default_factory=list
    )

    normalized_events: list[Event] = field(
        default_factory=list
    )

    events: list[Event] = field(
        default_factory=list
    )

    evidence: list[Evidence] = field(
        default_factory=list
    )

    timeline: ProjectTimeline | None = None

    dependencies: DependencyGraph | None = None

    context: ProjectContext | None = None

    decisions: list[Decision] = field(
        default_factory=list
    )

    conflicts: list[Conflict] = field(
        default_factory=list
    )

    confidence: dict[str, ConfidenceResult] = field(
        default_factory=dict
    )

    takeover_report: TakeoverReport | None = None

    def to_dict(self) -> dict:
        """
        Convert the complete pipeline result into a JSON-safe
        dictionary for APIs and n8n.
        """

        return {
            "raw_event_count": len(
                self.raw_events
            ),
            "normalized_event_count": len(
                self.normalized_events
            ),
            "event_count": len(
                self.events
            ),
            "evidence_count": len(
                self.evidence
            ),
            "events": [
                event.model_dump(mode="json")
                for event in self.events
            ],
            "evidence": [
                item.model_dump(mode="json")
                for item in self.evidence
            ],
            "timeline": (
                self.timeline.to_list()
                if self.timeline
                else []
            ),
            "dependencies": (
                self.dependencies.to_list()
                if self.dependencies
                else []
            ),
            "context": (
                self.context.to_dict()
                if self.context
                else None
            ),
            "decisions": [
                decision.model_dump(mode="json")
                for decision in self.decisions
            ],
            "conflicts": [
                conflict.to_dict()
                for conflict in self.conflicts
            ],
            "confidence": {
                key: value.to_dict()
                for key, value in self.confidence.items()
            },
            "takeover_report": (
                self.takeover_report.model_dump(
                    mode="json"
                )
                if self.takeover_report
                else None
            ),
        }


class ContextRecoveryService:
    """
    End-to-end Context Recovery Engine.

    Current source:
        GitHub

    Processing:
        GitHub
          ↓
        Normalize
          ↓
        Deduplicate
          ↓
        Evidence
          ↓
        Timeline
          ↓
        Dependencies
          ↓
        Context
          ↓
        Decisions
          ↓
        Conflicts
          ↓
        Confidence
          ↓
        Takeover Report

    The service intentionally keeps each processing stage
    deterministic and separately inspectable.
    """

    def __init__(
        self,
        github_connector: GitHubConnector | None = None,
        normalizer: EventNormalizer | None = None,
        deduplicator: EventDeduplicator | None = None,
        evidence_extractor: EvidenceExtractor | None = None,
        timeline_engine: TimelineEngine | None = None,
        dependency_engine: DependencyEngine | None = None,
        context_engine: ContextEngine | None = None,
        decision_engine: DecisionEngine | None = None,
        conflict_detector: ConflictDetector | None = None,
        confidence_engine: ConfidenceEngine | None = None,
        takeover_engine: TakeoverEngine | None = None,
    ):
        self.github_connector = github_connector

        self.normalizer = (
            normalizer
            if normalizer is not None
            else EventNormalizer()
        )

        self.deduplicator = (
            deduplicator
            if deduplicator is not None
            else EventDeduplicator()
        )

        self.evidence_extractor = (
            evidence_extractor
            if evidence_extractor is not None
            else EvidenceExtractor()
        )

        self.timeline_engine = (
            timeline_engine
            if timeline_engine is not None
            else TimelineEngine()
        )

        self.dependency_engine = (
            dependency_engine
            if dependency_engine is not None
            else DependencyEngine()
        )

        self.context_engine = (
            context_engine
            if context_engine is not None
            else ContextEngine()
        )

        self.decision_engine = (
            decision_engine
            if decision_engine is not None
            else DecisionEngine()
        )

        self.conflict_detector = (
            conflict_detector
            if conflict_detector is not None
            else ConflictDetector()
        )

        self.confidence_engine = (
            confidence_engine
            if confidence_engine is not None
            else ConfidenceEngine()
        )

        self.takeover_engine = (
            takeover_engine
            if takeover_engine is not None
            else TakeoverEngine()
        )

    # =========================================================
    # GitHub setup
    # =========================================================

    @classmethod
    def from_github_token(
        cls,
        token: str | None = None,
    ) -> "ContextRecoveryService":
        """
        Create the service using a GitHub token.

        If token is not supplied, GITHUB_TOKEN is read from
        the environment.
        """

        token = token or os.getenv(
            "GITHUB_TOKEN"
        )

        if not token:
            raise ValueError(
                "GITHUB_TOKEN is not configured."
            )

        return cls(
            github_connector=GitHubConnector(
                token
            )
        )

    # =========================================================
    # Main GitHub pipeline
    # =========================================================

    def analyze_github_repository(
        self,
        repository: str,
        *,
        commit_limit: int = 100,
        pr_limit: int = 100,
        issue_limit: int = 100,
        target_role: str | None = None,
        previous_owner: str | None = None,
    ) -> ServiceResult:
        """
        Collect and analyze a GitHub repository.

        Example:

            service.analyze_github_repository(
                "owner/repository",
                target_role="Backend Developer",
                previous_owner="alice",
            )
        """

        if not repository or not repository.strip():
            raise ValueError(
                "repository is required."
            )

        if self.github_connector is None:
            raise RuntimeError(
                "GitHub connector is not configured. "
                "Use ContextRecoveryService.from_github_token()."
            )

        # -----------------------------------------------------
        # 1. Collect raw GitHub events
        # -----------------------------------------------------

        raw_events = (
            self.github_connector.collect_all(
                repository=repository.strip(),
                commit_limit=commit_limit,
                pr_limit=pr_limit,
                issue_limit=issue_limit,
            )
        )

        # -----------------------------------------------------
        # 2. Normalize
        # -----------------------------------------------------

        normalized_events = (
            self.normalizer.normalize_many(
                raw_events
            )
        )

        # -----------------------------------------------------
        # 3. Deduplicate
        # -----------------------------------------------------

        events = self.deduplicator.deduplicate(
            normalized_events
        )

        # -----------------------------------------------------
        # 4. Extract evidence
        # -----------------------------------------------------

        evidence = (
            self.evidence_extractor.extract_many(
                events
            )
        )

        # -----------------------------------------------------
        # 5. Build timeline
        # -----------------------------------------------------

        timeline = self.timeline_engine.build(
            events=events,
            evidence=evidence,
        )

        # -----------------------------------------------------
        # 6. Build dependency graph
        # -----------------------------------------------------

        dependencies = self.dependency_engine.build(
            events=events,
            evidence=evidence,
        )

        # -----------------------------------------------------
        # 7. Reconstruct project context
        # -----------------------------------------------------

        context = self.context_engine.build(
            events=events,
            evidence=evidence,
            timeline=timeline,
            dependencies=dependencies,
        )

        # -----------------------------------------------------
        # 8. Extract decisions
        # -----------------------------------------------------

        decisions = (
            self.decision_engine.extract_decisions(
                events=events,
                evidence=evidence,
            )
        )

        # -----------------------------------------------------
        # 9. Detect conflicts
        # -----------------------------------------------------

        conflicts = (
            self.conflict_detector.detect(
                decisions
            )
        )

        # -----------------------------------------------------
        # 10. Calculate confidence
        # -----------------------------------------------------

        confidence: dict[
            str,
            ConfidenceResult,
        ] = {}

        for item in evidence:

            confidence[item.id] = (
                self.confidence_engine.evaluate_evidence(
                    evidence=item,
                    events=events,
                    conflicts=conflicts,
                )
            )

        # Decision-level confidence is also stored.
        for decision in decisions:

            confidence_key = (
                f"decision:{decision.id}"
            )

            confidence[confidence_key] = (
                self.confidence_engine.evaluate_decision(
                    decision=decision,
                    evidence=evidence,
                    events=events,
                    conflicts=conflicts,
                )
            )

        # -----------------------------------------------------
        # 11. Generate takeover report
        # -----------------------------------------------------

        takeover_report = (
            self.takeover_engine.generate(
                context=context,
                decisions=decisions,
                conflicts=conflicts,
                confidence=confidence,
                target_role=target_role,
                previous_owner=previous_owner,
            )
        )

        return ServiceResult(
            raw_events=raw_events,
            normalized_events=normalized_events,
            events=events,
            evidence=evidence,
            timeline=timeline,
            dependencies=dependencies,
            context=context,
            decisions=decisions,
            conflicts=conflicts,
            confidence=confidence,
            takeover_report=takeover_report,
        )

    # =========================================================
    # Existing Event API
    # =========================================================

    def analyze_events(
        self,
        events: list[Event],
        *,
        target_role: str | None = None,
        previous_owner: str | None = None,
    ) -> ServiceResult:
        """
        Run the processing pipeline on already collected events.

        This is useful for:

        - Slack
        - Discord
        - Notion
        - Google Drive
        - Tests
        - Future n8n webhook input
        """

        raw_events = list(events)

        # -----------------------------------------------------
        # Normalize
        # -----------------------------------------------------

        normalized_events = (
            self.normalizer.normalize_many(
                raw_events
            )
        )

        # -----------------------------------------------------
        # Deduplicate
        # -----------------------------------------------------

        normalized_events = list(
            normalized_events
        )

        unique_events = (
            self.deduplicator.deduplicate(
                normalized_events
            )
        )

        # -----------------------------------------------------
        # Evidence
        # -----------------------------------------------------

        evidence = (
            self.evidence_extractor.extract_many(
                unique_events
            )
        )

        # -----------------------------------------------------
        # Timeline
        # -----------------------------------------------------

        timeline = self.timeline_engine.build(
            events=unique_events,
            evidence=evidence,
        )

        # -----------------------------------------------------
        # Dependencies
        # -----------------------------------------------------

        dependencies = self.dependency_engine.build(
            events=unique_events,
            evidence=evidence,
        )

        # -----------------------------------------------------
        # Context
        # -----------------------------------------------------

        context = self.context_engine.build(
            events=unique_events,
            evidence=evidence,
            timeline=timeline,
            dependencies=dependencies,
        )

        # -----------------------------------------------------
        # Decisions
        # -----------------------------------------------------

        decisions = (
            self.decision_engine.extract_decisions(
                events=unique_events,
                evidence=evidence,
            )
        )

        # -----------------------------------------------------
        # Conflicts
        # -----------------------------------------------------

        conflicts = (
            self.conflict_detector.detect(
                decisions
            )
        )

        # -----------------------------------------------------
        # Confidence
        # -----------------------------------------------------

        confidence: dict[
            str,
            ConfidenceResult,
        ] = {}

        for item in evidence:

            confidence[item.id] = (
                self.confidence_engine.evaluate_evidence(
                    evidence=item,
                    events=unique_events,
                    conflicts=conflicts,
                )
            )

        for decision in decisions:

            confidence[
                f"decision:{decision.id}"
            ] = (
                self.confidence_engine.evaluate_decision(
                    decision=decision,
                    evidence=evidence,
                    events=unique_events,
                    conflicts=conflicts,
                )
            )

        # -----------------------------------------------------
        # Takeover
        # -----------------------------------------------------

        takeover_report = (
            self.takeover_engine.generate(
                context=context,
                decisions=decisions,
                conflicts=conflicts,
                confidence=confidence,
                target_role=target_role,
                previous_owner=previous_owner,
            )
        )

        return ServiceResult(
            raw_events=raw_events,
            normalized_events=normalized_events,
            events=unique_events,
            evidence=evidence,
            timeline=timeline,
            dependencies=dependencies,
            context=context,
            decisions=decisions,
            conflicts=conflicts,
            confidence=confidence,
            takeover_report=takeover_report,
        )