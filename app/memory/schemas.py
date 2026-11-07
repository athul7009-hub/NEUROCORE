
from datetime import datetime, timezone
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemoryStatus(str, Enum):
    COMPLETED = "completed"
    FAILED = "failed"


class MemorySensitivity(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    LEGACY_UNCLASSIFIED = "legacy_unclassified"


class MemorySource(str, Enum):
    COORDINATOR = "coordinator"
    SYSTEM = "system"
    LEGACY = "legacy"


class EpisodicMemoryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    intent: str = Field(min_length=1)
    status: MemoryStatus
    agent_name: str = Field(min_length=1)
    summary: str = Field(min_length=1, max_length=1000)

    created_at: datetime
    completed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL
    source: MemorySource = MemorySource.COORDINATOR
