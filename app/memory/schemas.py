
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class EpisodicMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    intent: str = Field(min_length=1)
    status: MemoryStatus
    agent_name: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)

    created_at: datetime
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
