
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.memory.schemas import (
    MemoryLifecycleStatus,
    MemoryStatus,
)


class MemoryContextItem(BaseModel):
    """A selected memory provided to an agent."""

    model_config = ConfigDict(extra="forbid")

    source_task_id: UUID
    intent: str = Field(min_length=1)
    status: MemoryStatus
    agent_name: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)
    completed_at: datetime
    lifecycle_status: MemoryLifecycleStatus = (
        MemoryLifecycleStatus.ACTIVE
    )


class MemoryContext(BaseModel):
    """A bounded collection of memories for a specific agent task."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    recipient_agent: str = Field(min_length=1)
    memories: list[MemoryContextItem] = Field(
        default_factory=list,
        max_length=10,
    )
