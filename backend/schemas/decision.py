from enum import Enum

from pydantic import BaseModel, Field


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class Decision(BaseModel):
    id: str
    title: str
    decision: str
    problem: str | None = None
    alternatives: list[str] = Field(default_factory=list)
    reason: str | None = None
    status: DecisionStatus = DecisionStatus.PROPOSED
    evidence_ids: list[str] = Field(default_factory=list)
    decided_by: list[str] = Field(default_factory=list)
    project: str | None = None
    metadata: dict = Field(default_factory=dict)