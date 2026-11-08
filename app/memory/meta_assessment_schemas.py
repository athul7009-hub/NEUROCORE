
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.memory.meta_schemas import MetaMemoryStalenessStatus


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


class MetaMemoryAssessment(BaseModel):
    """Advisory assessment of an existing memory's metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    quality_score: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
    )

    assessment_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    staleness_status: MetaMemoryStalenessStatus

    assessed_at: datetime = Field(default_factory=current_timestamp)

    rationale: str = Field(min_length=1, max_length=500)

    @field_validator("assessed_at")
    @classmethod
    def validate_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware.")
        return value

    @field_validator("rationale")
    @classmethod
    def validate_rationale(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("rationale cannot be blank.")
        return value.strip()
