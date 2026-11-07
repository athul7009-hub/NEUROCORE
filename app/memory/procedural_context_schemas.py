
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.memory.procedural_schemas import (
    ProceduralMemorySource,
    ProceduralMemoryStep,
)


class ProceduralMemoryContextItem(BaseModel):
    """A validated procedure selected for an agent."""

    model_config = ConfigDict(extra="forbid")

    procedure_id: UUID
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    when_to_use: str = Field(min_length=1, max_length=1000)
    steps: list[ProceduralMemoryStep] = Field(min_length=1, max_length=50)
    confidence: float = Field(ge=0.0, le=1.0)
    source: ProceduralMemorySource


class ProceduralMemoryContext(BaseModel):
    """Bounded procedural memory context for an agent."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    recipient_agent: str = Field(min_length=1)
    memories: list[ProceduralMemoryContextItem] = Field(
        default_factory=list,
        max_length=10,
    )
