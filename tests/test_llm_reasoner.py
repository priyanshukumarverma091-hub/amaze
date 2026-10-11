# tests/test_llm_reasoner.py

import json

from backend.reasoning.llm_reasoner import (
    LLMReasoner,
    ReasoningInput,
)
from backend.reasoning.context_engine import ProjectContext
from backend.schemas import (
    Decision,
    DecisionStatus,
)


def make_input():
    """
    Create a minimal valid ReasoningInput for testing.
    """

    context = ProjectContext(
        project="TestProject",
        summary="A project for testing knowledge recovery.",
        current_state="in_progress",

        completed_work=[],
        active_work=[],
        blocked_work=[],
        planned_work=[],
        abandoned_work=[],
        unknown_work=[],

        important_decisions=[],
        dependencies=[],
        risks=[],
        evidence_ids=[],
    )

    decision = Decision(
        id="dec-1",
        title="Choose database",
        decision="Use PostgreSQL",
        problem="The project needs a relational database.",
        alternatives=["MongoDB"],
        reason="PostgreSQL provides the required relational features.",
        status=DecisionStatus.ACCEPTED,
        evidence_ids=["ev-1"],
        decided_by=["alice"],
        project="TestProject",
        metadata={},
    )

    return ReasoningInput(
        context=context,
        decisions=[decision],
        conflicts=[],
        confidence={},
    )


def valid_report():
    """
    Return a valid TakeoverReport-compatible dictionary.
    """

    return {
        "id": "takeover-1",
        "project": "TestProject",
        "target_role": "backend developer",
        "previous_owner": "alice",
        "project_summary": "A project for testing knowledge recovery.",
        "current_state": "in_progress",
        "completed_work": [],
        "active_work": [],
        "blocked_work": [],
        "dependencies": [],
        "important_decisions": [
            "Use PostgreSQL"
        ],
        "risks": [],
        "recommended_first_steps": [
            "Review the existing project context."
        ],
        "evidence_ids": [
            "ev-1"
        ],
    }


def test_reasoning_input_to_dict():
    """
    ReasoningInput should convert correctly into a dictionary.
    """

    data = make_input().to_dict()

    assert "context" in data
    assert "decisions" in data
    assert "conflicts" in data
    assert "confidence" in data

    assert data["context"]["project"] == "TestProject"
    assert data["context"]["current_state"] == "in_progress"

    assert "completed_work" in data["context"]
    assert "active_work" in data["context"]
    assert "blocked_work" in data["context"]
    assert "planned_work" in data["context"]
    assert "abandoned_work" in data["context"]
    assert "unknown_work" in data["context"]

    assert len(data["decisions"]) == 1
    assert data["decisions"][0]["id"] == "dec-1"
    assert data["decisions"][0]["decision"] == "Use PostgreSQL"


def test_prompt_contains_structured_context():
    """
    Prompt should contain project and takeover information.
    """

    reasoner = LLMReasoner()

    prompt = reasoner.build_prompt(
        make_input(),
        target_role="backend developer",
        previous_owner="alice",
    )

    assert "TestProject" in prompt
    assert "backend developer" in prompt
    assert "alice" in prompt
    assert "PostgreSQL" in prompt

    assert "STRUCTURED PROJECT DATA" in prompt
    assert "Return ONLY valid JSON" in prompt


def test_parse_valid_json_response():
    """
    Valid JSON should be converted into TakeoverReport.
    """

    reasoner = LLMReasoner()

    response = json.dumps(valid_report())

    report = reasoner.parse_response(response)

    assert report.id == "takeover-1"
    assert report.project == "TestProject"
    assert report.target_role == "backend developer"
    assert report.previous_owner == "alice"


def test_parse_markdown_json_response():
    """
    JSON wrapped inside Markdown code fences should also work.
    """

    reasoner = LLMReasoner()

    response = f""

{json.dumps(valid_report())}