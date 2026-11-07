from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.memory.semantic_schemas import SemanticMemorySource


class SemanticMemoryContextItem(BaseModel):
    """A validated semantic fact provided to an agent."""

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID
    subject: str = Field(min_length=1, max_length=300)
    predicate: str = Field(min_length=1, max_length=150)
    object: str = Field(min_length=1, max_length=1000)
    confidence: float = Field(ge=0.0, le=1.0)
    source: SemanticMemorySource
    validated_at: datetime
    validated_by: str = Field(min_length=1)


class SemanticMemoryContext(BaseModel):
    """A bounded collection of validated semantic knowledge."""

    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    recipient_agent: str = Field(min_length=1)
    memories: list[SemanticMemoryContextItem] = Field(
        default_factory=list,
        max_length=10,
    )