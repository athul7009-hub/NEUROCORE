from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)


class ProspectiveMemoryContextItem(BaseModel):
    """A pending intention selected for an agent."""

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    action: str = Field(min_length=1, max_length=1000)

    trigger_type: ProspectiveTriggerType
    trigger_condition: str | None = Field(
        default=None,
        max_length=1000,
    )

    priority: ProspectiveMemoryPriority
    status: ProspectiveMemoryStatus

    due_at: datetime | None = None
    expires_at: datetime | None = None


class ProspectiveMemoryContext(BaseModel):
    """Bounded prospective memory context for an agent."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    recipient_agent: str = Field(min_length=1)

    memories: list[ProspectiveMemoryContextItem] = Field(
        default_factory=list,
        max_length=10,
    )