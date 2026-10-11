from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.schemas import Event, Evidence, Decision
from backend.processing.timeline import TimelineEngine
from backend.processing.dependencies import DependencyEngine
from backend.reasoning.context_engine import ContextEngine
from backend.reasoning.llm_reasoner import LLMReasoner


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent
INDEX_FILE = BASE_DIR / "index.html"


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Context Recovery Engine",
    description="Backend API for project context recovery and team handover.",
    version="1.0.0",
)


# Allow the local frontend origins used during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# REQUEST SCHEMAS
# ============================================================

class IngestRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)


class ReasonRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    target_role: str = "New Team Member"
    previous_owner: str | None = None


class HandoffRequest(BaseModel):
    events: list[dict[str, Any]] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    decisions: list[dict[str, Any]] = Field(default_factory=list)
    target_role: str = "New Team Member"
    previous_owner: str | None = None


# ============================================================
# FRONTEND
# ============================================================

@app.get("/", include_in_schema=False)
def root():
    if not INDEX_FILE.exists():
        raise HTTPException(
            status_code=404,
            detail="index.html not found",
        )

    return FileResponse(INDEX_FILE)


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "context-recovery-engine",
    }


# ============================================================
# SERVICE INFO
# ============================================================

@app.get("/api/info")
def info():
    return {
        "service": "Context Recovery Engine",
        "status": "running",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "frontend": (
            "connected"
            if INDEX_FILE.exists()
            else "missing"
        ),
    }


# ============================================================
# GENERIC INGESTION
# ============================================================

@app.post("/api/ingest")
def ingest(request: IngestRequest):

    return {
        "status": "success",
        "events_received": len(request.events),
        "events": request.events,
    }


# ============================================================
# GITHUB INGESTION
# ============================================================

@app.post("/api/ingest/github")
def ingest_github(request: IngestRequest):

    github_events = []

    for event in request.events:
        event_copy = dict(event)
        event_copy["source"] = "github"
        github_events.append(event_copy)

    return {
        "status": "success",
        "source": "github",
        "events_received": len(github_events),
        "events": github_events,
    }


# ============================================================
# AI REASONING PIPELINE
# ============================================================

def run_reasoning_pipeline(
    request: ReasonRequest,
) -> dict[str, Any]:

    # --------------------------------------------------------
    # 1. Parse events
    # --------------------------------------------------------

    events = [
        Event.model_validate(event)
        for event in request.events
    ]

    # --------------------------------------------------------
    # 2. Parse evidence
    # --------------------------------------------------------

    evidence = [
        Evidence.model_validate(item)
        for item in request.evidence
    ]

    # --------------------------------------------------------
    # 3. Parse decisions
    # --------------------------------------------------------

    decisions = [
        Decision.model_validate(item)
        for item in request.decisions
    ]

    # --------------------------------------------------------
    # 4. Build timeline
    # --------------------------------------------------------

    timeline = TimelineEngine.build(
        events=events,
        evidence=evidence,
    )

    # --------------------------------------------------------
    # 5. Build dependency graph
    # --------------------------------------------------------

    dependency_graph = DependencyEngine.build(
        events=events,
        evidence=evidence,
    )

    # --------------------------------------------------------
    # 6. Build project context
    # --------------------------------------------------------

    context = ContextEngine.build(
        events=events,
        evidence=evidence,
        timeline=timeline,
        dependencies=dependency_graph,
    )

    # --------------------------------------------------------
    # 7. Confidence
    # --------------------------------------------------------

    confidence = {}

    # --------------------------------------------------------
    # 8. LLM Reasoner
    # --------------------------------------------------------

    reasoner = LLMReasoner()

    reasoning_input = reasoner.create_reasoning_input(
        context=context,
        decisions=decisions,
        conflicts=[],
        confidence=confidence,
    )

    # --------------------------------------------------------
    # 9. Generate takeover report
    # --------------------------------------------------------

    result = reasoner.generate_takeover_report(
        reasoning_input=reasoning_input,
        target_role=request.target_role,
        previous_owner=request.previous_owner,
    )

    # --------------------------------------------------------
    # 10. Check AI result
    # --------------------------------------------------------

    if not result.success:
        raise HTTPException(
            status_code=500,
            detail={
                "message": "AI reasoning failed",
                "error": result.error,
            },
        )

    # --------------------------------------------------------
    # 11. Return result
    # --------------------------------------------------------

    return {
        "target_role": request.target_role,
        "previous_owner": request.previous_owner,
        "timeline_events": len(timeline.items),
        "evidence_count": len(evidence),
        "decision_count": len(decisions),
        "dependencies": len(
            dependency_graph.dependencies
        ),
        "report": (
            result.report.model_dump()
            if result.report
            else None
        ),
    }


# ============================================================
# AI REASONING API
# ============================================================

@app.post("/api/reason")
def reason(request: ReasonRequest):

    try:

        result = run_reasoning_pipeline(request)

        return {
            "status": "success",
            **result,
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Reasoning pipeline failed",
                "error": str(exc),
            },
        )


# ============================================================
# NEW MEMBER HANDOFF
# ============================================================

@app.post("/api/handoff")
def handoff(request: HandoffRequest):

    try:

        reasoning_request = ReasonRequest(
            events=request.events,
            evidence=request.evidence,
            decisions=request.decisions,
            target_role=request.target_role,
            previous_owner=request.previous_owner,
        )

        result = run_reasoning_pipeline(
            reasoning_request
        )

        return {
            "status": "success",
            "handoff_status": "READY",
            "project": "RETRO-AI",
            "incoming_member": request.target_role,
            "previous_owner": request.previous_owner,
            "report": result["report"],
            "pipeline": {
                "timeline_events": result["timeline_events"],
                "evidence_count": result["evidence_count"],
                "decision_count": result["decision_count"],
                "dependencies": result["dependencies"],
            },
        }

    except HTTPException:
        raise

    except Exception as exc:

        raise HTTPException(
            status_code=500,
            detail={
                "message": "Handoff generation failed",
                "error": str(exc),
            },
        )


# ============================================================
# SYSTEM STATUS
# ============================================================

@app.get("/api/status")
def status():

    return {
        "service": "Context Recovery Engine",
        "backend": "online",
        "frontend": (
            "connected"
            if INDEX_FILE.exists()
            else "missing"
        ),
        "n8n_ingestion": "ready",
        "github_ingestion": "ready",
        "documentation_adapter": "ready",
        "discord_adapter": "ready",
        "slack_adapter": "ready",
        "processing_pipeline": "connected",
        "ai_reasoning": "connected",
        "handoff_engine": "connected",
    }


# ============================================================
# N8N WORKFLOW STATUS
# ============================================================

@app.get("/api/workflows")
def workflows():

    return {
        "status": "ready",
        "workflows": [
            {
                "id": "08",
                "name": "Evidence Extraction",
                "status": "READY",
                "source": "GitHub",
            },
            {
                "id": "09",
                "name": "New Member Handoff",
                "status": "READY",
                "source": "Handoff",
            },
            {
                "id": "10",
                "name": "Documentation Context",
                "status": "ADAPTER",
                "source": "Documentation",
            },
            {
                "id": "11",
                "name": "Chat Context",
                "status": "ADAPTER",
                "source": "Discord / Slack",
            },
            {
                "id": "12",
                "name": "Final Context Orchestrator",
                "status": "READY_FOR_DEMO",
                "source": "n8n",
            },
        ],
    }