
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from app.memory.schemas import MemorySensitivity


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


# -------------------------------
# Procedural memory types
# -------------------------------

class ProceduralMemoryStatus(str, Enum):
    CANDIDATE = "candidate"
    VALIDATED = "validated"
    DEPRECATED = "deprecated"


class ProceduralMemorySource(str, Enum):
    EPISODIC = "episodic"
    DOCUMENT = "document"
    USER = "user"
    SYSTEM = "system"
    AGENT = "agent"


# -------------------------------
# Individual procedure step
# -------------------------------

class ProceduralMemoryStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(ge=1)
    instruction: str = Field(min_length=1, max_length=1000)
    expected_outcome: str | None = Field(
        default=None,
        max_length=1000,
    )


# -------------------------------
# Procedural memory record
# -------------------------------

class ProceduralMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    procedure_id: UUID = Field(default_factory=uuid4)

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    when_to_use: str = Field(min_length=1, max_length=1000)

    steps: list[ProceduralMemoryStep] = Field(
        min_length=1,
        max_length=50,
    )

    confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    status: ProceduralMemoryStatus = (
        ProceduralMemoryStatus.CANDIDATE
    )

    sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL
    source: ProceduralMemorySource

    source_task_id: UUID | None = None
    source_reference: str | None = Field(
        default=None,
        max_length=1000,
    )

    created_at: datetime = Field(default_factory=current_timestamp)
    updated_at: datetime = Field(default_factory=current_timestamp)

    validated_at: datetime | None = None
    validated_by: str | None = Field(
        default=None,
        min_length=1,
    )

    is_protected: bool = False

    @model_validator(mode="after")
    def validate_procedure(self):
        # Ensure procedure steps are ordered and uniquely numbered.
        step_numbers = [
            step.step_number for step in self.steps
        ]

        expected_numbers = list(
            range(1, len(self.steps) + 1)
        )

        if sorted(step_numbers) != expected_numbers:
            raise ValueError(
                "Procedure steps must have unique, sequential "
                "step numbers starting from 1."
            )

        # Validated procedures require validation metadata.
        if self.status == ProceduralMemoryStatus.VALIDATED:
            if self.validated_at is None or not self.validated_by:
                raise ValueError(
                    "Validated procedures require validated_at "
                    "and validated_by."
                )

        # Non-validated procedures cannot retain validation metadata.
        elif self.validated_at is not None or self.validated_by is not None:
            raise ValueError(
                "Non-validated procedures cannot contain "
                "validation metadata."
            )

        return self
