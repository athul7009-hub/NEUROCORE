
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.memory.meta_schemas import MetaMemoryType


class MemoryIdentityAvailability(str, Enum):
    AVAILABLE = "available"
    INACTIVE = "inactive"
    EXPIRED = "expired"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"


class MemoryIdentityRequest(BaseModel):
    """Identifies a memory without requesting its content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_type: MetaMemoryType
    memory_id: UUID
    task_id: UUID | None = None

    @model_validator(mode="after")
    def validate_task_id(self):
        if self.memory_type == MetaMemoryType.WORKING:
            if self.task_id is None:
                raise ValueError(
                    "task_id is required for working memory."
                )
        elif self.task_id is not None:
            raise ValueError(
                "task_id is only allowed for working memory."
            )

        return self


class MemoryIdentityAssessment(BaseModel):
    """Describes memory identity and lifecycle availability."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    memory_type: MetaMemoryType
    memory_id: UUID
    exists: bool
    lifecycle_status: str | None = Field(
        default=None,
        max_length=50,
    )
    availability: MemoryIdentityAvailability
    task_id: UUID | None = None

    @model_validator(mode="after")
    def validate_assessment(self):
        if self.availability == MemoryIdentityAvailability.NOT_FOUND:
            if self.exists:
                raise ValueError(
                    "A not-found assessment cannot indicate existence."
                )
            if self.lifecycle_status is not None:
                raise ValueError(
                    "A not-found assessment cannot have a lifecycle status."
                )

        elif not self.exists:
            raise ValueError(
                "Existing availability states require an existing memory."
            )

        if self.memory_type == MetaMemoryType.WORKING:
            if self.task_id is None:
                raise ValueError(
                    "task_id is required for working memory assessments."
                )
        elif self.task_id is not None:
            raise ValueError(
                "task_id is only allowed for working memory assessments."
            )

        return self
