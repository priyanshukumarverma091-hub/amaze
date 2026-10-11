import json
from dataclasses import dataclass
from typing import Any, Callable

from backend.schemas import Decision, TakeoverReport
from backend.reasoning.context_engine import ProjectContext
from backend.reasoning.conflict_detector import Conflict
from backend.reasoning.confidence import ConfidenceResult
from backend.reasoning.openrouter_provider import OpenRouterProvider


@dataclass
class ReasoningInput:
    context: ProjectContext
    decisions: list[Decision]
    conflicts: list[Conflict]
    confidence: dict[str, ConfidenceResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "context": {
                "project": self.context.project,
                "summary": self.context.summary,
                "current_state": self.context.current_state,
                "completed_work": self.context.completed_work,
                "active_work": self.context.active_work,
                "blocked_work": self.context.blocked_work,
                "planned_work": self.context.planned_work,
                "abandoned_work": self.context.abandoned_work,
                "unknown_work": self.context.unknown_work,
                "important_decisions": self.context.important_decisions,
                "dependencies": self.context.dependencies,
                "risks": self.context.risks,
                "evidence_ids": self.context.evidence_ids,
            },
            "decisions": [
                {
                    "id": decision.id,
                    "title": decision.title,
                    "decision": decision.decision,
                    "problem": decision.problem,
                    "alternatives": decision.alternatives,
                    "reason": decision.reason,
                    "status": decision.status.value,
                    "evidence_ids": decision.evidence_ids,
                    "decided_by": decision.decided_by,
                    "project": decision.project,
                    "metadata": decision.metadata,
                }
                for decision in self.decisions
            ],
            "conflicts": [
                conflict.to_dict()
                for conflict in self.conflicts
            ],
            "confidence": {
                key: result.to_dict()
                for key, result in self.confidence.items()
            },
        }


@dataclass
class LLMReasoningResult:
    success: bool
    report: TakeoverReport | None = None
    raw_response: str | None = None
    error: str | None = None


class LLMReasoner:

    SYSTEM_INSTRUCTION = """
You are the reasoning engine of a Project Context Recovery System.

Your job is to reconstruct project knowledge for a new team member.

STRICT RULES:

1. Use ONLY the structured information supplied in the input.
2. Do NOT invent facts, people, tasks, technologies, decisions,
   dependencies, dates, or project status.
3. Do NOT assume information that is not explicitly present.
4. Preserve evidence IDs whenever information is included.
5. If information is uncertain, keep it uncertain.
6. Report conflicts explicitly.
7. Do not silently resolve contradictory decisions.
8. Do not create unsupported alternatives or reasons.
9. Keep the output grounded in the supplied context.
10. Return ONLY valid JSON.
11. The JSON must conform to the TakeoverReport structure.

The report should help a new team member understand:

- what the project is
- what has already been completed
- what is currently active
- what is blocked
- what is planned
- what was abandoned
- important decisions
- dependencies
- risks
- recommended first steps
- supporting evidence

Every important claim should be traceable to evidence IDs when available.
""".strip()

    def __init__(
        self,
        llm_callable: Callable[[str], str] | None = None,
    ):
        # If a custom LLM is supplied, use it.
        # Otherwise, use the OpenRouter provider configured through .env.
        self.llm_callable = llm_callable or OpenRouterProvider()

    def build_prompt(
        self,
        reasoning_input: ReasoningInput,
        target_role: str | None = None,
        previous_owner: str | None = None,
    ) -> str:

        payload = reasoning_input.to_dict()

        payload["takeover"] = {
            "target_role": target_role,
            "previous_owner": previous_owner,
        }

        serialized_data = json.dumps(
            payload,
            indent=2,
            ensure_ascii=False,
            default=str,
        )

        prompt = f"""
{self.SYSTEM_INSTRUCTION}

STRUCTURED PROJECT DATA
=======================

{serialized_data}

TAKEOVER INFORMATION
====================

Target role:
{target_role if target_role else "Not specified"}

Previous owner:
{previous_owner if previous_owner else "Not specified"}

TASK
====

Generate a project takeover report for the new team member.

The report must contain:

- id
- project
- target_role
- previous_owner
- project_summary
- current_state
- completed_work
- active_work
- blocked_work
- dependencies
- important_decisions
- risks
- recommended_first_steps
- evidence_ids

For work items, use ONLY these statuses:

- done
- in_progress
- blocked
- planned
- abandoned
- unknown

Do not add information that is not supported by the structured data.

If target_role or previous_owner is not specified,
use null where appropriate.

Return ONLY valid JSON.
""".strip()

        return prompt

    def parse_response(
        self,
        response: str,
    ) -> TakeoverReport:

        if not response:
            raise ValueError(
                "LLM returned an empty response."
            )

        cleaned = response.strip()

        if cleaned.startswith("```"):
            lines = cleaned.splitlines()

            if lines and lines[0].strip().startswith("```"):
                lines = lines[1:]

            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]

            cleaned = "\n".join(lines).strip()

        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()

        try:
            parsed = json.loads(cleaned)

        except json.JSONDecodeError as exc:
            raise ValueError(
                f"LLM response is not valid JSON: {exc}"
            ) from exc

        if not isinstance(parsed, dict):
            raise ValueError(
                "LLM response JSON must be an object."
            )

        try:
            return TakeoverReport.model_validate(parsed)

        except Exception as exc:
            raise ValueError(
                "LLM response does not match "
                f"TakeoverReport schema: {exc}"
            ) from exc

    def generate_takeover_report(
        self,
        reasoning_input: ReasoningInput,
        target_role: str | None = None,
        previous_owner: str | None = None,
    ) -> LLMReasoningResult:

        try:
            prompt = self.build_prompt(
                reasoning_input=reasoning_input,
                target_role=target_role,
                previous_owner=previous_owner,
            )

        except Exception as exc:
            return LLMReasoningResult(
                success=False,
                report=None,
                raw_response=None,
                error=f"Prompt construction failed: {exc}",
            )

        if self.llm_callable is None:
            return LLMReasoningResult(
                success=False,
                report=None,
                raw_response=None,
                error="No LLM provider configured.",
            )

        try:
            raw_response = self.llm_callable(prompt)

        except Exception as exc:
            return LLMReasoningResult(
                success=False,
                report=None,
                raw_response=None,
                error=f"LLM provider failed: {exc}",
            )

        try:
            report = self.parse_response(raw_response)

        except Exception as exc:
            return LLMReasoningResult(
                success=False,
                report=None,
                raw_response=raw_response,
                error=str(exc),
            )

        return LLMReasoningResult(
            success=True,
            report=report,
            raw_response=raw_response,
            error=None,
        )