from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.schemas import (
    Decision,
    DecisionStatus,
    Evidence,
    EvidenceType,
    Event,
)


@dataclass
class DecisionChain:
    """
    Represents the reconstructed lifecycle of a decision.

    problem
        ↓
    discussion/evidence
        ↓
    decision
        ↓
    implementation/result
    """

    decision: Decision

    problem_evidence: list[str] = field(
        default_factory=list
    )

    supporting_evidence: list[str] = field(
        default_factory=list
    )

    implementation_event_ids: list[str] = field(
        default_factory=list
    )

    result_evidence: list[str] = field(
        default_factory=list
    )

    def to_dict(self) -> dict:
        return {
            "decision": self.decision.model_dump(),
            "problem_evidence": self.problem_evidence,
            "supporting_evidence": self.supporting_evidence,
            "implementation_event_ids": (
                self.implementation_event_ids
            ),
            "result_evidence": self.result_evidence,
        }


class DecisionEngine:
    """
    Reconstructs project decisions from events and evidence.

    This engine is intentionally conservative:
    - It only creates decisions when evidence indicates one.
    - It preserves source evidence.
    - It does not invent reasons or alternatives.
    - It can later be enhanced by an LLM.
    """

    DECISION_PATTERNS = [
        r"\bwe decided\b",
        r"\bwe will use\b",
        r"\bwe'll use\b",
        r"\bwe chose\b",
        r"\bwe choose\b",
        r"\bwe selected\b",
        r"\bdecision\b",
        r"\bagreed to\b",
        r"\bchosen\b",
        r"\bselected\b",
    ]

    IMPLEMENTATION_PATTERNS = [
        r"\bimplemented\b",
        r"\bimplementing\b",
        r"\bimplemented this\b",
        r"\badded\b",
        r"\bupdated\b",
        r"\bdeployed\b",
        r"\bmerged\b",
        r"\bcompleted\b",
        r"\bfixed\b",
    ]

    def extract_decisions(
        self,
        events: list[Event],
        evidence: list[Evidence],
    ) -> list[Decision]:

        decision_evidence = [
            item
            for item in evidence
            if item.evidence_type
            == EvidenceType.DECISION
        ]

        decisions: list[Decision] = []

        for index, item in enumerate(
            decision_evidence,
            start=1,
        ):

            source_events = [
                event
                for event in events
                if event.id in item.source_event_ids
            ]

            if not source_events:
                continue

            source_event = source_events[0]

            title = self._build_title(
                source_event,
                item,
                index,
            )

            decision_text = self._extract_decision_text(
                source_event
            )

            problem = self._find_problem(
                source_event,
                events,
                evidence,
            )

            reason = self._extract_reason(
                source_event
            )

            alternatives = (
                self._extract_alternatives(
                    source_event
                )
            )

            status = self._infer_status(
                source_event,
                events,
            )

            decided_by = []

            if source_event.actor:
                decided_by.append(
                    source_event.actor
                )

            decision = Decision(
                id=f"decision_{source_event.id}_{index}",
                title=title,
                decision=decision_text,
                problem=problem,
                alternatives=alternatives,
                reason=reason,
                status=status,
                evidence_ids=[item.id],
                decided_by=decided_by,
                project=source_event.project,
                metadata={
                    "source_event_id": source_event.id,
                    "source": source_event.source,
                    "source_url": source_event.url,
                },
            )

            decisions.append(decision)

        return self._deduplicate_decisions(
            decisions
        )

    def build_chains(
        self,
        decisions: list[Decision],
        events: list[Event],
        evidence: list[Evidence],
    ) -> list[DecisionChain]:

        chains = []

        for decision in decisions:

            source_event_id = decision.metadata.get(
                "source_event_id"
            )

            supporting_evidence = []

            problem_evidence = []

            result_evidence = []

            for item in evidence:

                if (
                    source_event_id
                    in item.source_event_ids
                ):
                    supporting_evidence.append(
                        item.id
                    )

                if (
                    item.evidence_type
                    == EvidenceType.PROBLEM
                ):
                    if self._related_to_decision(
                        decision,
                        item,
                    ):
                        problem_evidence.append(
                            item.id
                        )

                if (
                    item.evidence_type
                    in {
                        EvidenceType.SOLUTION,
                        EvidenceType.STATUS_CHANGE,
                    }
                ):
                    if self._related_to_decision(
                        decision,
                        item,
                    ):
                        result_evidence.append(
                            item.id
                        )

            implementation_event_ids = (
                self._find_implementation_events(
                    decision,
                    events,
                )
            )

            chains.append(
                DecisionChain(
                    decision=decision,
                    problem_evidence=problem_evidence,
                    supporting_evidence=(
                        supporting_evidence
                    ),
                    implementation_event_ids=(
                        implementation_event_ids
                    ),
                    result_evidence=result_evidence,
                )
            )

        return chains

    @classmethod
    def _build_title(
        cls,
        event: Event,
        evidence: Evidence,
        index: int,
    ) -> str:

        if event.title:
            return event.title

        if evidence.claim:
            return evidence.claim[:200]

        return f"Decision {index}"

    @classmethod
    def _extract_decision_text(
        cls,
        event: Event,
    ) -> str:

        text = (
            event.content
            or event.title
            or ""
        ).strip()

        if not text:
            return "Decision identified from project evidence."

        # Try to extract the sentence containing the
        # decision language.
        sentences = re.split(
            r"(?<=[.!?])\s+",
            text,
        )

        for sentence in sentences:

            lowered = sentence.lower()

            if any(
                re.search(pattern, lowered)
                for pattern in cls.DECISION_PATTERNS
            ):
                return sentence.strip()

        return text[:500]

    @staticmethod
    def _find_problem(
        source_event: Event,
        events: list[Event],
        evidence: list[Evidence],
    ) -> str | None:

        source_time = source_event.timestamp

        candidates = []

        for item in evidence:

            if item.evidence_type != EvidenceType.PROBLEM:
                continue

            for event in events:

                if event.id not in item.source_event_ids:
                    continue

                if event.id == source_event.id:
                    continue

                if event.timestamp <= source_time:
                    candidates.append(
                        (
                            source_time - event.timestamp,
                            item,
                        )
                    )

        if not candidates:
            return None

        candidates.sort(
            key=lambda value: value[0]
        )

        return candidates[0][1].claim

    @staticmethod
    def _extract_reason(
        event: Event,
    ) -> str | None:

        text = event.content or ""

        patterns = [
            r"\bbecause\s+(.+?)(?:[.!?]|$)",
            r"\bsince\s+(.+?)(?:[.!?]|$)",
            r"\bdue to\s+(.+?)(?:[.!?]|$)",
            r"\breason\s*(?:is|:)\s*(.+?)(?:[.!?]|$)",
        ]

        for pattern in patterns:

            match = re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:
                return match.group(1).strip()

        return None

    @staticmethod
    def _extract_alternatives(
        event: Event,
    ) -> list[str]:

        text = event.content or ""

        alternatives = []

        patterns = [
            r"(?:instead of|rather than)\s+([^.,;]+)",
            r"(?:alternative|alternatives)\s*:\s*([^.!?]+)",
            r"(?:considered)\s+([^.!?]+)",
        ]

        for pattern in patterns:

            matches = re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            for match in matches:

                value = match.strip()

                if value and value not in alternatives:
                    alternatives.append(value)

        return alternatives

    @staticmethod
    def _infer_status(
        source_event: Event,
        events: list[Event],
    ) -> DecisionStatus:

        metadata = source_event.metadata or {}

        if metadata.get("merged") is True:
            return DecisionStatus.IMPLEMENTED

        if (
            source_event.event_type.value == "issue"
            and metadata.get("state") == "closed"
        ):
            return DecisionStatus.IMPLEMENTED

        text = (
            f"{source_event.title or ''} "
            f"{source_event.content or ''}"
        ).lower()

        if any(
            word in text
            for word in [
                "implemented",
                "implemented this",
                "deployed",
                "merged",
                "completed",
                "fixed",
            ]
        ):
            return DecisionStatus.IMPLEMENTED

        if any(
            word in text
            for word in [
                "rejected",
                "reject",
                "discarded",
            ]
        ):
            return DecisionStatus.REJECTED

        if any(
            word in text
            for word in [
                "superseded",
                "replaced by",
                "changed to",
            ]
        ):
            return DecisionStatus.SUPERSEDED

        if any(
            word in text
            for word in [
                "accepted",
                "agreed",
            ]
        ):
            return DecisionStatus.ACCEPTED

        return DecisionStatus.PROPOSED

    @staticmethod
    def _related_to_decision(
        decision: Decision,
        evidence: Evidence,
    ) -> bool:

        decision_text = (
            f"{decision.title} "
            f"{decision.decision} "
            f"{decision.problem or ''}"
        ).lower()

        evidence_text = (
            f"{evidence.claim} "
            f"{evidence.description or ''}"
        ).lower()

        decision_words = {
            word
            for word in re.findall(
                r"\b[a-zA-Z0-9_-]{4,}\b",
                decision_text,
            )
        }

        evidence_words = {
            word
            for word in re.findall(
                r"\b[a-zA-Z0-9_-]{4,}\b",
                evidence_text,
            )
        }

        return bool(
            decision_words & evidence_words
        )

    @classmethod
    def _find_implementation_events(
        cls,
        decision: Decision,
        events: list[Event],
    ) -> list[str]:

        implementation_events = []

        decision_text = (
            f"{decision.title} "
            f"{decision.decision}"
        ).lower()

        decision_words = {
            word
            for word in re.findall(
                r"\b[a-zA-Z0-9_-]{4,}\b",
                decision_text,
            )
        }

        decision_event_id = decision.metadata.get(
            "source_event_id"
        )

        source_event = next(
            (
                event
                for event in events
                if event.id == decision_event_id
            ),
            None,
        )

        if source_event is None:
            return []

        for event in events:

            if event.id == decision_event_id:
                continue

            if event.timestamp < source_event.timestamp:
                continue

            text = (
                f"{event.title or ''} "
                f"{event.content or ''}"
            ).lower()

            has_implementation_language = any(
                re.search(
                    pattern,
                    text,
                )
                for pattern in cls.IMPLEMENTATION_PATTERNS
            )

            if not has_implementation_language:
                continue

            event_words = {
                word
                for word in re.findall(
                    r"\b[a-zA-Z0-9_-]{4,}\b",
                    text,
                )
            }

            if decision_words & event_words:
                implementation_events.append(
                    event.id
                )

        return implementation_events

    @staticmethod
    def _deduplicate_decisions(
        decisions: list[Decision],
    ) -> list[Decision]:

        unique = []
        seen = set()

        for decision in decisions:

            key = (
                decision.project,
                decision.decision.strip().lower(),
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(decision)

        return unique