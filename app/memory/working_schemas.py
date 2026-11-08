
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.memory.schemas import MemorySensitivity


class WorkingMemoryEntryType(str, Enum):
    OBSERVATION = "observation"
    INTERMEDIATE_RESULT = "intermediate_result"
    TASK_STATE = "task_state"
    AGENT_NOTE = "agent_note"


class WorkingMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID = Field(default_factory=uuid4)
    task_id: UUID

    key: str = Field(min_length=1, max_length=200)
    entry_type: WorkingMemoryEntryType
    content: dict[str, Any] = Field(default_factory=dict)

    source_agent: str = Field(min_length=1, max_length=100)

    sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    expires_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self):
        timestamps = (
            self.created_at,
            self.updated_at,
            self.expires_at,
        )

        if any(
            timestamp.tzinfo is None
            or timestamp.utcoffset() is None
            for timestamp in timestamps
        ):
            raise ValueError(
                "Working memory timestamps must be timezone-aware."
            )

        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot be earlier than created_at."
            )

        if self.expires_at <= self.created_at:
            raise ValueError(
                "expires_at must be later than created_at."
            )

        return self


class WorkingMemoryContextItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_id: UUID
    key: str = Field(min_length=1, max_length=200)
    entry_type: WorkingMemoryEntryType
    content: dict[str, Any]
    source_agent: str = Field(min_length=1, max_length=100)


class WorkingMemoryContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    recipient_agent: str = Field(min_length=1, max_length=100)

    entries: list[WorkingMemoryContextItem] = Field(
        default_factory=list,
        max_length=20,
    )
