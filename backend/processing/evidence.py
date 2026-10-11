from __future__ import annotations

import re

from backend.schemas import Event, EventType
from backend.schemas.evidence import Evidence, EvidenceType


class EvidenceExtractor:
    """
    Extract structured evidence from normalized events.

    This first version is deterministic and does not require
    an external LLM.

    Later, an LLM can enrich or validate these results.
    """

    def extract(
        self,
        event: Event,
    ) -> list[Evidence]:

        evidence: list[Evidence] = []

        evidence.extend(
            self._extract_event_evidence(event)
        )

        evidence.extend(
            self._extract_keyword_evidence(event)
        )

        return self._remove_duplicate_evidence(
            evidence
        )

    def extract_many(
        self,
        events: list[Event],
    ) -> list[Evidence]:

        all_evidence: list[Evidence] = []

        for event in events:
            all_evidence.extend(
                self.extract(event)
            )

        return self._remove_duplicate_evidence(
            all_evidence
        )

    def _extract_event_evidence(
        self,
        event: Event,
    ) -> list[Evidence]:

        evidence = []

        if event.event_type == EventType.COMMIT:
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.FACT,
                    claim=f"Code change: {event.title or 'Untitled commit'}",
                    description=event.content,
                    confidence=0.95,
                )
            )

        elif event.event_type == EventType.PULL_REQUEST:
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.TASK,
                    claim=f"Pull request: {event.title or 'Untitled PR'}",
                    description=event.content,
                    confidence=0.95,
                )
            )

        elif event.event_type == EventType.ISSUE:
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.PROBLEM,
                    claim=f"Issue: {event.title or 'Untitled issue'}",
                    description=event.content,
                    confidence=0.90,
                )
            )

        elif event.event_type == EventType.DOCUMENT:
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.FACT,
                    claim=event.title or "Project document",
                    description=event.content,
                    confidence=0.75,
                )
            )

        elif event.event_type == EventType.MESSAGE:
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.FACT,
                    claim=event.title or "Team message",
                    description=event.content,
                    confidence=0.60,
                )
            )

        return evidence

    def _extract_keyword_evidence(
        self,
        event: Event,
    ) -> list[Evidence]:

        text = self._combined_text(event)

        if not text:
            return []

        evidence = []

        if self._contains_any(
            text,
            [
                "decided",
                "decision",
                "we will",
                "we'll",
                "agreed",
                "chosen",
                "choose",
                "selected",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.DECISION,
                    claim=self._build_claim(
                        "Possible decision",
                        event,
                    ),
                    description=event.content,
                    confidence=0.70,
                )
            )

        if self._contains_any(
            text,
            [
                "bug",
                "error",
                "issue",
                "problem",
                "failed",
                "failure",
                "broken",
                "not working",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.PROBLEM,
                    claim=self._build_claim(
                        "Possible problem",
                        event,
                    ),
                    description=event.content,
                    confidence=0.70,
                )
            )

        if self._contains_any(
            text,
            [
                "fixed",
                "fix",
                "resolved",
                "solution",
                "solved",
                "working now",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.SOLUTION,
                    claim=self._build_claim(
                        "Possible solution",
                        event,
                    ),
                    description=event.content,
                    confidence=0.70,
                )
            )

        if self._contains_any(
            text,
            [
                "todo",
                "to do",
                "task",
                "implement",
                "implementing",
                "need to",
                "needs to",
                "should add",
                "must add",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.TASK,
                    claim=self._build_claim(
                        "Possible task",
                        event,
                    ),
                    description=event.content,
                    confidence=0.65,
                )
            )

        if self._contains_any(
            text,
            [
                "depends on",
                "dependency",
                "requires",
                "required by",
                "blocked by",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.DEPENDENCY,
                    claim=self._build_claim(
                        "Possible dependency",
                        event,
                    ),
                    description=event.content,
                    confidence=0.65,
                )
            )

        if self._contains_any(
            text,
            [
                "completed",
                "done",
                "finished",
                "merged",
                "deployed",
            ],
        ):
            evidence.append(
                self._create_evidence(
                    event=event,
                    evidence_type=EvidenceType.STATUS_CHANGE,
                    claim=self._build_claim(
                        "Possible completed work",
                        event,
                    ),
                    description=event.content,
                    confidence=0.80,
                )
            )

        return evidence

    @staticmethod
    def _combined_text(
        event: Event,
    ) -> str:

        parts = [
            event.title or "",
            event.content or "",
        ]

        return " ".join(parts).lower()

    @staticmethod
    def _contains_any(
        text: str,
        keywords: list[str],
    ) -> bool:

        return any(
            re.search(
                rf"\b{re.escape(keyword)}\b",
                text,
            )
            for keyword in keywords
        )

    @staticmethod
    def _build_claim(
        prefix: str,
        event: Event,
    ) -> str:

        title = event.title or event.content[:120]

        return f"{prefix}: {title}"

    @staticmethod
    def _create_evidence(
        event: Event,
        evidence_type: EvidenceType,
        claim: str,
        description: str | None,
        confidence: float,
    ) -> Evidence:

        evidence_id = (
            f"evidence_{event.id}_"
            f"{evidence_type.value}"
        )

        return Evidence(
            id=evidence_id,
            evidence_type=evidence_type,
            claim=claim,
            description=description,
            source_event_ids=[event.id],
            confidence=confidence,
            project=event.project,
            metadata={
                "source": event.source,
                "source_id": event.source_id,
                "event_type": event.event_type.value,
                "url": event.url,
                "actor": event.actor,
            },
        )

    @staticmethod
    def _remove_duplicate_evidence(
        evidence: list[Evidence],
    ) -> list[Evidence]:

        unique = []
        seen = set()

        for item in evidence:

            key = (
                item.id,
                item.evidence_type.value,
                item.claim,
            )

            if key in seen:
                continue

            seen.add(key)
            unique.append(item)

        return unique