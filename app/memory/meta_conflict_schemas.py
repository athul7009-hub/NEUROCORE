
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


class MetaMemoryConflictType(str, Enum):
    FACTUAL = "factual"
    PROCEDURAL = "procedural"
    TEMPORAL = "temporal"
    OTHER = "other"


class MetaMemoryConflictStatus(str, Enum):
    DETECTED = "detected"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    RESOLVED = "resolved"


class MetaMemoryConflictRecord(BaseModel):
    """Stores a potential conflict between two existing memories."""

    model_config = ConfigDict(extra="forbid")

    conflict_id: UUID = Field(default_factory=uuid4)

    memory_type_a: str
    memory_id_a: str = Field(min_length=1, max_length=100)

    memory_type_b: str
    memory_id_b: str = Field(min_length=1, max_length=100)

    conflict_type: MetaMemoryConflictType

    confidence_score: float = Field(ge=0.0, le=1.0)

    rationale: str = Field(min_length=1, max_length=500)

    status: MetaMemoryConflictStatus = (
        MetaMemoryConflictStatus.DETECTED
    )

    detected_at: datetime = Field(default_factory=current_timestamp)
    reviewed_at: datetime | None = None

    created_at: datetime = Field(default_factory=current_timestamp)
    updated_at: datetime = Field(default_factory=current_timestamp)

    @field_validator("memory_type_a", "memory_type_b")
    @classmethod
    def validate_memory_type(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Memory type cannot be blank.")
        return value

    @field_validator("memory_id_a", "memory_id_b")
    @classmethod
    def validate_memory_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Memory ID cannot be blank.")
        return value

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Rationale cannot be blank.")
        return value

    @field_validator(
        "detected_at",
        "reviewed_at",
        "created_at",
        "updated_at",
    )
    @classmethod
    def validate_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None or value.utcoffset() is None
        ):
            raise ValueError("Timestamps must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def validate_conflict(self):
        if (
            self.memory_type_a == self.memory_type_b
            and self.memory_id_a == self.memory_id_b
        ):
            raise ValueError(
                "A memory cannot conflict with itself."
            )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot precede created_at."
            )

        if self.status == MetaMemoryConflictStatus.DETECTED:
            if self.reviewed_at is not None:
                raise ValueError(
                    "Detected conflicts cannot have reviewed_at."
                )
        elif self.reviewed_at is None:
            raise ValueError(
                "Reviewed conflicts must have reviewed_at."
            )

        return self
