
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.memory.schemas import MemorySensitivity


class SemanticMemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


class SemanticMemorySource(str, Enum):
    EPISODIC = "episodic"
    DOCUMENT = "document"
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


class SemanticMemoryRecord(BaseModel):
    """A structured knowledge record."""

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID = Field(default_factory=uuid4)

    subject: str = Field(min_length=1, max_length=300)
    predicate: str = Field(min_length=1, max_length=150)
    object: str = Field(min_length=1, max_length=1000)

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    status: SemanticMemoryStatus = SemanticMemoryStatus.CANDIDATE

    sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL

    source: SemanticMemorySource
    source_task_id: UUID | None = None
    source_reference: str | None = Field(default=None, max_length=1000)

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    validated_at: datetime | None = None
    validated_by: str | None = Field(default=None, max_length=150)

    is_protected: bool = False

    @model_validator(mode="after")
    def validate_validation_state(self):
        if self.status == SemanticMemoryStatus.VALIDATED:
            if self.validated_at is None:
                raise ValueError(
                    "Validated memories must have validated_at."
                )

            if not self.validated_by:
                raise ValueError(
                    "Validated memories must have validated_by."
                )

        elif self.validated_at is not None or self.validated_by is not None:
            raise ValueError(
                "Only validated memories can have validation metadata."
            )

        return self
