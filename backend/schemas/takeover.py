from enum import Enum

from pydantic import BaseModel, Field


class WorkStatus(str, Enum):
    DONE = "done"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    PLANNED = "planned"
    ABANDONED = "abandoned"
    UNKNOWN = "unknown"


class WorkItem(BaseModel):
    title: str
    description: str | None = None

    status: WorkStatus

    evidence_ids: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)


class TakeoverReport(BaseModel):
    id: str

    project: str

    target_role: str

    previous_owner: str | None = None

    project_summary: str

    current_state: str

    completed_work: list[WorkItem] = Field(default_factory=list)
    active_work: list[WorkItem] = Field(default_factory=list)
    blocked_work: list[WorkItem] = Field(default_factory=list)

    dependencies: list[str] = Field(default_factory=list)

    important_decisions: list[str] = Field(default_factory=list)

    risks: list[str] = Field(default_factory=list)

    recommended_first_steps: list[str] = Field(default_factory=list)

    evidence_ids: list[str] = Field(default_factory=list)