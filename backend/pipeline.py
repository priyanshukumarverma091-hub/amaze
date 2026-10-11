from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from backend.schemas import (
    Decision,
    Evidence,
    Event,
    TakeoverReport,
)

from backend.reasoning.context_engine import ProjectContext
from backend.reasoning.confidence import ConfidenceResult
from backend.reasoning.conflict_detector import Conflict
from backend.reasoning.decision_engine import DecisionEngine
from backend.reasoning.takeover_engine import TakeoverEngine


@dataclass
class PipelineResult:
    """
    Complete output of the Context Recovery pipeline.

    Every intermediate stage is preserved so that the same
    results can later be exposed through an API, dashboard,
    n8n workflow, or LLM reasoning layer.
    """

    events: list[Event] = field(default_factory=list)

    evidence: list[Evidence] = field(default_factory=list)

    decisions: list[Decision] = field(default_factory=list)

    conflicts: list[Conflict] = field(default_factory=list)

    confidence: dict[str, ConfidenceResult] = field(
        default_factory=dict
    )

    context: ProjectContext | None = None

    takeover_report: TakeoverReport | None = None


class ContextRecoveryPipeline:
    """
    Main orchestration layer for the Context Recovery Engine.

    Current pipeline:

        Events
          ↓
        Evidence
          ↓
        Decision Engine
          ↓
        Context Engine
          ↓
        Conflict Detection
          ↓
        Confidence
          ↓
        Takeover Engine
          ↓
        Takeover Report

    The LLM is intentionally NOT used here.
    """

    def __init__(
        self,
        decision_engine: DecisionEngine | None = None,
        takeover_engine: TakeoverEngine | None = None,
    ):
        self.decision_engine = (
            decision_engine
            if decision_engine is not None
            else DecisionEngine()
        )

        self.takeover_engine = (
            takeover_engine
            if takeover_engine is not None
            else TakeoverEngine()
        )

    def run(
        self,
        *,
        events: Iterable[Event],
        evidence: Iterable[Evidence],
        context: ProjectContext,
        decisions: Iterable[Decision] | None = None,
        conflicts: Iterable[Conflict] | None = None,
        confidence: dict[str, ConfidenceResult] | None = None,
        target_role: str | None = None,
        previous_owner: str | None = None,
    ) -> PipelineResult:
        """
        Execute the structured Context Recovery pipeline.

        Existing engines remain responsible for their own logic.
        This class only connects their outputs.
        """

        events = list(events)
        evidence = list(evidence)

        conflicts = list(
            conflicts
            if conflicts is not None
            else []
        )

        confidence = dict(
            confidence
            if confidence is not None
            else {}
        )

        # ----------------------------------------------------------
        # STEP 1
        # Decision reconstruction
        # ----------------------------------------------------------

        if decisions is None:
            decisions = self.decision_engine.extract_decisions(
                events,
                evidence,
            )
        else:
            decisions = list(decisions)

        # ----------------------------------------------------------
        # STEP 2
        # Deterministic takeover generation
        # ----------------------------------------------------------

        takeover_report = self.takeover_engine.generate(
            context=context,
            decisions=decisions,
            conflicts=conflicts,
            confidence=confidence,
            target_role=target_role,
            previous_owner=previous_owner,
        )

        # ----------------------------------------------------------
        # STEP 3
        # Return complete pipeline result
        # ----------------------------------------------------------

        return PipelineResult(
            events=events,
            evidence=evidence,
            decisions=decisions,
            conflicts=conflicts,
            confidence=confidence,
            context=context,
            takeover_report=takeover_report,
        )