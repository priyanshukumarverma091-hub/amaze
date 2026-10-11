from enum import Enum

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    FACT = "fact"
    DECISION = "decision"
    PROBLEM = "problem"
    SOLUTION = "solution"
    REQUIREMENT = "requirement"
    TASK = "task"
    DEPENDENCY = "dependency"
    STATUS_CHANGE = "status_change"


class Evidence(BaseModel):
    id: str

    evidence_type: EvidenceType

    claim: str
    description: str | None = None

    source_event_ids: list[str] = Field(default_factory=list)

    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0
    )

    project: str | None = None

    metadata: dict = Field(default_factory=dict)