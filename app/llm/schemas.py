
from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


class ReasoningRequest(BaseModel):
    """Validated input provided to the LLM reasoning service."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID = Field(default_factory=uuid4)
    task_id: UUID

    agent_name: str = Field(min_length=1, max_length=100)
    objective: str = Field(min_length=1, max_length=5000)

    context: str = Field(default="", max_length=12000)

    created_at: datetime = Field(default_factory=current_timestamp)
    @field_validator("agent_name", "objective")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Value cannot contain only whitespace.")

        return value

class ReasoningResponse(BaseModel):
    """Structured reasoning proposal returned by the LLM."""

    model_config = ConfigDict(extra="forbid")

    request_id: UUID
    task_id: UUID

    reasoning_summary: str = Field(min_length=1, max_length=5000)

    proposed_steps: list[str] = Field(
        min_length=1,
        max_length=20,
    )

    confidence: float = Field(ge=0.0, le=1.0)

    limitations: list[str] = Field(
        default_factory=list,
        max_length=10,
    )

    created_at: datetime = Field(default_factory=current_timestamp)
    @field_validator("reasoning_summary")
    @classmethod
    def validate_summary(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Reasoning summary cannot be empty.")

        return value

    @field_validator("proposed_steps", "limitations")
    @classmethod
    def validate_text_lists(cls, values: list[str]) -> list[str]:
        cleaned_values = [value.strip() for value in values]

        if any(not value for value in cleaned_values):
            raise ValueError("List items cannot contain only whitespace.")

        return cleaned_values