from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

router = APIRouter()


# ============================================================
# REQUEST MODELS
# ============================================================

class Evidence(BaseModel):
    id: str
    evidence_type: str
    claim: str
    description: str = ""
    source_event_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    project: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Event(BaseModel):
    id: str
    source: str
    source_id: str
    event_type: str
    actor: str = "unknown"
    timestamp: str
    project: str = ""
    title: str = ""
    content: str = ""
    url: Optional[str] = None
    references: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    id: str
    title: str
    decision: str
    problem: Optional[str] = None
    alternatives: List[str] = Field(default_factory=list)
    reason: Optional[str] = None
    status: str = "unknown"
    evidence_ids: List[str] = Field(default_factory=list)
    decided_by: List[str] = Field(default_factory=list)
    project: str = ""
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ReasonRequest(BaseModel):
    events: List[Event] = Field(default_factory=list)
    evidence: List[Evidence] = Field(default_factory=list)
    decisions: List[Decision] = Field(default_factory=list)

    target_role: str = "New Team Member"
    previous_owner: Optional[str] = None


# ============================================================
# HELPER
# ============================================================

def evidence_count(evidence: List[Evidence], evidence_type: str) -> int:
    return sum(
        1 for item in evidence
        if item.evidence_type == evidence_type
    )


def build_report(
    events: List[Event],
    evidence: List[Evidence],
    decisions: List[Decision],
    target_role: str,
    previous_owner: Optional[str],
):
    problems = [
        e for e in evidence
        if e.evidence_type == "problem"
    ]

    solutions = [
        e for e in evidence
        if e.evidence_type == "solution"
    ]

    tasks = [
        e for e in evidence
        if e.evidence_type == "task"
    ]

    dependencies = [
        e for e in evidence
        if e.evidence_type == "dependency"
    ]

    status_changes = [
        e for e in evidence
        if e.evidence_type == "status_change"
    ]

    report = {
        "project": events[0].project if events else "Context Recovery Engine",

        "handoff": {
            "target_role": target_role,
            "previous_owner": previous_owner,
        },

        "project_state": {
            "total_events": len(events),
            "total_evidence": len(evidence),
            "total_decisions": len(decisions),
            "problems": len(problems),
            "solutions": len(solutions),
            "tasks": len(tasks),
            "dependencies": len(dependencies),
            "status_changes": len(status_changes),
        },

        "current_tasks": [
            {
                "claim": task.claim,
                "description": task.description,
                "confidence": task.confidence,
                "source_event_ids": task.source_event_ids,
            }
            for task in tasks
        ],

        "known_problems": [
            {
                "claim": problem.claim,
                "description": problem.description,
                "confidence": problem.confidence,
                "source_event_ids": problem.source_event_ids,
            }
            for problem in problems
        ],

        "implemented_solutions": [
            {
                "claim": solution.claim,
                "description": solution.description,
                "confidence": solution.confidence,
                "source_event_ids": solution.source_event_ids,
            }
            for solution in solutions
        ],

        "dependencies": [
            {
                "claim": dependency.claim,
                "description": dependency.description,
                "confidence": dependency.confidence,
                "source_event_ids": dependency.source_event_ids,
            }
            for dependency in dependencies
        ],

        "decisions": [
            {
                "title": decision.title,
                "decision": decision.decision,
                "status": decision.status,
                "decided_by": decision.decided_by,
                "evidence_ids": decision.evidence_ids,
            }
            for decision in decisions
        ],

        "recent_activity": [
            {
                "event_type": event.event_type,
                "title": event.title,
                "actor": event.actor,
                "timestamp": event.timestamp,
                "url": event.url,
            }
            for event in sorted(
                events,
                key=lambda x: x.timestamp,
                reverse=True
            )[:10]
        ],
    }

    return report


# ============================================================
# POST /api/reason
# ============================================================

@router.post("/reason")
def reason(request: ReasonRequest):

    report = build_report(
        events=request.events,
        evidence=request.evidence,
        decisions=request.decisions,
        target_role=request.target_role,
        previous_owner=request.previous_owner,
    )

    return {
        "status": "success",

        "target_role": request.target_role,

        "previous_owner": request.previous_owner,

        "timeline_events": len(request.events),

        "evidence_count": len(request.evidence),

        "decision_count": len(request.decisions),

        "dependencies": evidence_count(
            request.evidence,
            "dependency"
        ),

        "report": report,
    }