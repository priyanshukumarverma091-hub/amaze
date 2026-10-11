from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from backend.schemas import Decision, Evidence, Event
from backend.reasoning.conflict_detector import Conflict


@dataclass
class ConfidenceResult:
    """
    Final confidence assessment for a project claim.

    score:
        Final normalized confidence between 0 and 1.

    level:
        Human-readable confidence level.

    factors:
        Individual factors used to calculate the score.

    evidence_ids:
        Evidence supporting the assessment.

    warnings:
        Reasons why confidence may be reduced.
    """

    score: float

    level: str

    factors: dict[str, float] = field(
        default_factory=dict
    )

    evidence_ids: list[str] = field(
        default_factory=list
    )

    warnings: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "level": self.level,
            "factors": self.factors,
            "evidence_ids": self.evidence_ids,
            "warnings": self.warnings,
        }


class ConfidenceEngine:
    """
    Deterministic confidence engine.

    Confidence is calculated from:

        Evidence Strength
        +
        Source Reliability
        +
        Cross-source Agreement
        +
        Recency
        -
        Conflict Penalty

    The engine does not invent evidence.

    It only evaluates evidence already collected
    by the Context Recovery Engine.
    """

    # ---------------------------------------------------------
    # Default source reliability
    # ---------------------------------------------------------

    SOURCE_RELIABILITY = {
        "github": 0.95,
        "gitlab": 0.95,
        "bitbucket": 0.95,

        "document": 0.85,
        "docs": 0.85,

        "slack": 0.75,
        "discord": 0.70,

        "message": 0.65,

        "unknown": 0.50,
    }

    # ---------------------------------------------------------
    # Confidence weights
    #
    # These sum to 1.0 before conflict penalty.
    # ---------------------------------------------------------

    EVIDENCE_WEIGHT = 0.40
    SOURCE_WEIGHT = 0.25
    AGREEMENT_WEIGHT = 0.20
    RECENCY_WEIGHT = 0.15

    MAX_CONFLICT_PENALTY = 0.35

    # ---------------------------------------------------------
    # Public API
    # ---------------------------------------------------------

    def evaluate_evidence(
        self,
        evidence: Evidence,
        events: Iterable[Event] | None = None,
        conflicts: Iterable[Conflict] | None = None,
    ) -> ConfidenceResult:

        events = list(events or [])
        conflicts = list(conflicts or [])

        source_scores = []

        for event_id in evidence.source_event_ids:

            event = self._find_event(
                event_id,
                events,
            )

            if event is None:
                continue

            source_scores.append(
                self.source_reliability(
                    event.source
                )
            )

        if source_scores:
            source_score = sum(
                source_scores
            ) / len(source_scores)
        else:
            source_score = self.SOURCE_RELIABILITY[
                "unknown"
            ]

        evidence_score = self.evidence_strength(
            evidence
        )

        agreement_score = self.cross_source_agreement(
            evidence,
            events,
        )

        recency_score = self.recency_score(
            evidence,
            events,
        )

        conflict_penalty = self.conflict_penalty(
            evidence,
            conflicts,
        )

        raw_score = (
            evidence_score
            * self.EVIDENCE_WEIGHT
            + source_score
            * self.SOURCE_WEIGHT
            + agreement_score
            * self.AGREEMENT_WEIGHT
            + recency_score
            * self.RECENCY_WEIGHT
        )

        final_score = max(
            0.0,
            min(
                1.0,
                raw_score
                - conflict_penalty,
            ),
        )

        final_score = round(
            final_score,
            4,
        )

        warnings = []

        if evidence_score < 0.50:
            warnings.append(
                "Evidence strength is low."
            )

        if source_score < 0.60:
            warnings.append(
                "Source reliability is low."
            )

        if agreement_score < 0.50:
            warnings.append(
                "Evidence has limited cross-source agreement."
            )

        if recency_score < 0.50:
            warnings.append(
                "Evidence may be outdated."
            )

        if conflict_penalty > 0:
            warnings.append(
                "Related conflicting decisions were detected."
            )

        return ConfidenceResult(
            score=final_score,
            level=self.confidence_level(
                final_score
            ),
            factors={
                "evidence_strength": round(
                    evidence_score,
                    4,
                ),
                "source_reliability": round(
                    source_score,
                    4,
                ),
                "cross_source_agreement": round(
                    agreement_score,
                    4,
                ),
                "recency": round(
                    recency_score,
                    4,
                ),
                "conflict_penalty": round(
                    conflict_penalty,
                    4,
                ),
            },
            evidence_ids=[
                evidence.id
            ],
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # Evaluate a complete decision
    # ---------------------------------------------------------

    def evaluate_decision(
        self,
        decision: Decision,
        evidence: list[Evidence],
        events: list[Event] | None = None,
        conflicts: list[Conflict] | None = None,
    ) -> ConfidenceResult:

        related_evidence = [
            item
            for item in evidence
            if item.id in decision.evidence_ids
        ]

        if not related_evidence:

            return ConfidenceResult(
                score=0.0,
                level="very_low",
                factors={
                    "evidence_strength": 0.0,
                    "source_reliability": 0.0,
                    "cross_source_agreement": 0.0,
                    "recency": 0.0,
                    "conflict_penalty": 0.0,
                },
                evidence_ids=[],
                warnings=[
                    "Decision has no linked evidence."
                ],
            )

        results = []

        for item in related_evidence:

            result = self.evaluate_evidence(
                evidence=item,
                events=events,
                conflicts=conflicts,
            )

            results.append(result)

        score = sum(
            result.score
            for result in results
        ) / len(results)

        evidence_ids = []

        for item in related_evidence:
            if item.id not in evidence_ids:
                evidence_ids.append(
                    item.id
                )

        warnings = []

        for result in results:
            for warning in result.warnings:
                if warning not in warnings:
                    warnings.append(
                        warning
                    )

        return ConfidenceResult(
            score=round(
                score,
                4,
            ),
            level=self.confidence_level(
                score
            ),
            factors=self._average_factors(
                results
            ),
            evidence_ids=evidence_ids,
            warnings=warnings,
        )

    # ---------------------------------------------------------
    # Evidence strength
    # ---------------------------------------------------------

    @staticmethod
    def evidence_strength(
        evidence: Evidence,
    ) -> float:

        base = float(
            evidence.confidence
        )

        # Multiple source events provide stronger support.
        source_count = len(
            set(
                evidence.source_event_ids
            )
        )

        if source_count >= 3:
            base += 0.10

        elif source_count == 2:
            base += 0.05

        return max(
            0.0,
            min(
                1.0,
                base,
            ),
        )

    # ---------------------------------------------------------
    # Source reliability
    # ---------------------------------------------------------

    @classmethod
    def source_reliability(
        cls,
        source: str | None,
    ) -> float:

        if not source:
            return cls.SOURCE_RELIABILITY[
                "unknown"
            ]

        normalized = (
            source
            .strip()
            .lower()
        )

        return cls.SOURCE_RELIABILITY.get(
            normalized,
            cls.SOURCE_RELIABILITY[
                "unknown"
            ],
        )

    # ---------------------------------------------------------
    # Cross-source agreement
    # ---------------------------------------------------------

    @classmethod
    def cross_source_agreement(
        cls,
        evidence: Evidence,
        events: list[Event],
    ) -> float:

        source_names = set()

        for event_id in evidence.source_event_ids:

            event = cls._find_event(
                event_id,
                events,
            )

            if event is None:
                continue

            source_names.add(
                event.source.lower()
            )

        # No event metadata available.
        if not source_names:
            return 0.50

        # Multiple independent sources.
        if len(source_names) >= 3:
            return 1.00

        if len(source_names) == 2:
            return 0.85

        # Only one source.
        return 0.60

    # ---------------------------------------------------------
    # Recency
    # ---------------------------------------------------------

    @classmethod
    def recency_score(
        cls,
        evidence: Evidence,
        events: list[Event],
    ) -> float:

        timestamps = []

        for event_id in evidence.source_event_ids:

            event = cls._find_event(
                event_id,
                events,
            )

            if event is not None:
                timestamps.append(
                    event.timestamp
                )

        if not timestamps:
            return 0.50

        latest = max(
            timestamps
        )

        if latest.tzinfo is None:
            latest = latest.replace(
                tzinfo=timezone.utc
            )

        now = datetime.now(
            timezone.utc
        )

        age_days = (
            now - latest
        ).total_seconds() / 86400

        # Fresh evidence.
        if age_days <= 7:
            return 1.00

        # Recent evidence.
        if age_days <= 30:
            return 0.90

        if age_days <= 90:
            return 0.75

        if age_days <= 180:
            return 0.60

        if age_days <= 365:
            return 0.45

        # Very old evidence.
        return 0.30

    # ---------------------------------------------------------
    # Conflict penalty
    # ---------------------------------------------------------

    @classmethod
    def conflict_penalty(
        cls,
        evidence: Evidence,
        conflicts: list[Conflict],
    ) -> float:

        if not conflicts:
            return 0.0

        matching_conflicts = []

        for conflict in conflicts:

            if (
                evidence.id
                in conflict.evidence_ids
            ):
                matching_conflicts.append(
                    conflict
                )

        if not matching_conflicts:
            return 0.0

        # One conflict gives a moderate penalty.
        penalty = (
            0.15
            * len(matching_conflicts)
        )

        return min(
            cls.MAX_CONFLICT_PENALTY,
            penalty,
        )

    # ---------------------------------------------------------
    # Confidence level
    # ---------------------------------------------------------

    @staticmethod
    def confidence_level(
        score: float,
    ) -> str:

        if score >= 0.90:
            return "very_high"

        if score >= 0.75:
            return "high"

        if score >= 0.55:
            return "medium"

        if score >= 0.35:
            return "low"

        return "very_low"

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def _find_event(
        event_id: str,
        events: list[Event],
    ) -> Event | None:

        for event in events:

            if event.id == event_id:
                return event

        return None

    @staticmethod
    def _average_factors(
        results: list[ConfidenceResult],
    ) -> dict[str, float]:

        if not results:
            return {}

        keys = set()

        for result in results:
            keys.update(
                result.factors.keys()
            )

        averaged = {}

        for key in keys:

            values = [
                result.factors[key]
                for result in results
                if key in result.factors
            ]

            if values:
                averaged[key] = round(
                    sum(values)
                    / len(values),
                    4,
                )

        return averaged