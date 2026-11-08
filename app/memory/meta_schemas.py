
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


# -------------------------------
# Meta-memory types
# -------------------------------

class MetaMemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROCEDURAL = "procedural"
    WORKING = "working"
    PROSPECTIVE = "prospective"


class MetaMemoryStalenessStatus(str, Enum):
    UNKNOWN = "unknown"
    CURRENT = "current"
    REVIEW_RECOMMENDED = "review_recommended"


# -------------------------------
# Meta-memory record
# -------------------------------

class MetaMemoryRecord(BaseModel):
    """Stores management metadata about an existing memory."""

    model_config = ConfigDict(extra="forbid")

    meta_id: UUID = Field(default_factory=uuid4)

    memory_type: MetaMemoryType
    memory_id: str = Field(min_length=1, max_length=100)

    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    assessment_confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    usage_count: int = Field(default=0, ge=0)

    last_retrieved_at: datetime | None = None

    staleness_status: MetaMemoryStalenessStatus = (
        MetaMemoryStalenessStatus.UNKNOWN
    )

    last_assessed_at: datetime | None = None

    created_at: datetime = Field(default_factory=current_timestamp)
    updated_at: datetime = Field(default_factory=current_timestamp)

    # -------------------------------
    # Text validation
    # -------------------------------

    @field_validator("memory_id")
    @classmethod
    def validate_memory_id(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("memory_id cannot be blank.")
        return value

    # -------------------------------
    # Timestamp validation
    # -------------------------------

    @field_validator(
        "last_retrieved_at",
        "last_assessed_at",
        "created_at",
        "updated_at",
    )
    @classmethod
    def validate_timezone_aware(
        cls,
        value: datetime | None,
    ) -> datetime | None:
        if value is not None and (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "Timestamps must be timezone-aware."
            )
        return value

    # -------------------------------
    # Record validation
    # -------------------------------

    @model_validator(mode="after")
    def validate_meta_memory(self):
        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot be earlier than created_at."
            )

        has_confidence = self.assessment_confidence is not None
        has_assessed_at = self.last_assessed_at is not None
        has_quality_score = self.quality_score is not None

        if has_confidence != has_assessed_at:
            raise ValueError(
                "Assessment confidence and last_assessed_at "
                "must be provided together."
            )

        if has_quality_score and not has_confidence:
            raise ValueError(
                "A quality score requires assessment confidence "
                "and last_assessed_at."
            )

        return self