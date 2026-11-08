
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

from app.memory.schemas import MemorySensitivity


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


# -------------------------------
# Prospective memory types
# -------------------------------

class ProspectiveMemoryStatus(str, Enum):
    PENDING = "pending"
    TRIGGERED = "triggered"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ProspectiveTriggerType(str, Enum):
    TIME = "time"
    CONDITION = "condition"
    EVENT = "event"
    MANUAL = "manual"


class ProspectiveMemoryPriority(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class ProspectiveMemorySource(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


# -------------------------------
# Prospective memory record
# -------------------------------

class ProspectiveMemoryRecord(BaseModel):
    """Represents a future intention or pending action."""

    model_config = ConfigDict(extra="forbid")

    memory_id: UUID = Field(default_factory=uuid4)

    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=1000)
    action: str = Field(min_length=1, max_length=1000)

    trigger_type: ProspectiveTriggerType

    trigger_condition: str | None = Field(
        default=None,
        max_length=1000,
    )

    priority: ProspectiveMemoryPriority = (
        ProspectiveMemoryPriority.NORMAL
    )

    status: ProspectiveMemoryStatus = (
        ProspectiveMemoryStatus.PENDING
    )

    sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL

    source: ProspectiveMemorySource
    source_agent: str = Field(min_length=1, max_length=100)

    source_task_id: UUID | None = None

    created_at: datetime = Field(default_factory=current_timestamp)
    updated_at: datetime = Field(default_factory=current_timestamp)

    due_at: datetime | None = None
    expires_at: datetime | None = None

    triggered_at: datetime | None = None
    completed_at: datetime | None = None

    is_protected: bool = False

    # -------------------------------
    # Text validation
    # -------------------------------

    @field_validator(
        "title",
        "description",
        "action",
        "source_agent",
    )
    @classmethod
    def validate_nonblank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Text fields cannot be blank.")
        return value

    @field_validator("trigger_condition")
    @classmethod
    def validate_trigger_condition(
        cls,
        value: str | None,
    ) -> str | None:
        if value is not None and not value.strip():
            raise ValueError(
                "Trigger condition cannot be blank."
            )
        return value

    # -------------------------------
    # Timestamp validation
    # -------------------------------

    @field_validator(
        "created_at",
        "updated_at",
        "due_at",
        "expires_at",
        "triggered_at",
        "completed_at",
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
    def validate_prospective_memory(self):
        # Update time cannot precede creation.
        if self.updated_at < self.created_at:
            raise ValueError(
                "updated_at cannot be earlier than created_at."
            )

        # Due time cannot precede creation.
        if (
            self.due_at is not None
            and self.due_at < self.created_at
        ):
            raise ValueError(
                "due_at cannot be earlier than created_at."
            )

        # Expiration must follow creation.
        if (
            self.expires_at is not None
            and self.expires_at <= self.created_at
        ):
            raise ValueError(
                "expires_at must be later than created_at."
            )

        # Expiration cannot precede the scheduled due time.
        if (
            self.due_at is not None
            and self.expires_at is not None
            and self.expires_at < self.due_at
        ):
            raise ValueError(
                "expires_at cannot precede due_at."
            )

        # -------------------------------
        # Trigger consistency
        # -------------------------------

        if self.trigger_type == ProspectiveTriggerType.TIME:
            if self.due_at is None:
                raise ValueError(
                    "TIME triggers require due_at."
                )

            if self.trigger_condition is not None:
                raise ValueError(
                    "TIME triggers cannot have trigger_condition."
                )

        elif self.trigger_type in {
            ProspectiveTriggerType.EVENT,
            ProspectiveTriggerType.CONDITION,
        }:
            if self.trigger_condition is None:
                raise ValueError(
                    "EVENT and CONDITION triggers require "
                    "trigger_condition."
                )

            if self.due_at is not None:
                raise ValueError(
                    "EVENT and CONDITION triggers cannot have due_at."
                )

        elif self.trigger_type == ProspectiveTriggerType.MANUAL:
            if (
                self.due_at is not None
                or self.trigger_condition is not None
            ):
                raise ValueError(
                    "MANUAL triggers cannot have automatic "
                    "trigger details."
                )

        # -------------------------------
        # Lifecycle consistency
        # -------------------------------

        if self.status in {
            ProspectiveMemoryStatus.TRIGGERED,
            ProspectiveMemoryStatus.COMPLETED,
        }:
            if self.triggered_at is None:
                raise ValueError(
                    "TRIGGERED and COMPLETED memories require "
                    "triggered_at."
                )

        elif self.triggered_at is not None:
            raise ValueError(
                "Only TRIGGERED or COMPLETED memories can have "
                "triggered_at."
            )

        if self.status == ProspectiveMemoryStatus.COMPLETED:
            if self.completed_at is None:
                raise ValueError(
                    "COMPLETED memories require completed_at."
                )

        elif self.completed_at is not None:
            raise ValueError(
                "Only COMPLETED memories can have completed_at."
            )

        if (
            self.triggered_at is not None
            and self.due_at is not None
            and self.triggered_at < self.due_at
        ):
            raise ValueError(
                "triggered_at cannot precede due_at."
            )

        if (
            self.completed_at is not None
            and self.triggered_at is not None
            and self.completed_at < self.triggered_at
        ):
            raise ValueError(
                "completed_at cannot precede triggered_at."
            )

        if (
            self.status == ProspectiveMemoryStatus.EXPIRED
            and self.expires_at is None
        ):
            raise ValueError(
                "EXPIRED memories require expires_at."
            )

        return self
