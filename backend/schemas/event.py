from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventType(str, Enum):
    COMMIT = "commit"
    PULL_REQUEST = "pull_request"
    ISSUE = "issue"
    MESSAGE = "message"
    DOCUMENT = "document"
    TASK = "task"
    COMMENT = "comment"
    OTHER = "other"


class Event(BaseModel):
    id: str
    source: str
    source_id: str

    event_type: EventType

    actor: str | None = None
    timestamp: datetime

    project: str | None = None
    title: str | None = None
    content: str

    url: str | None = None

    references: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)