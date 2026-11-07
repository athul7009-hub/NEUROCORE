
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemorySensitivity,
    MemoryStatus,
)


@dataclass(frozen=True)
class RetentionAssessment:
    eligible: bool
    reasons: tuple[str, ...]


class MemoryRetentionPolicy:
    """Evaluates whether an episodic memory is eligible for archival."""

    PROTECTED_SENSITIVITIES = {
        MemorySensitivity.CONFIDENTIAL,
        MemorySensitivity.RESTRICTED,
        MemorySensitivity.LEGACY_UNCLASSIFIED,
    }

    def __init__(
        self,
        min_age_days: int | None = None,
        inactivity_days: int | None = None,
        max_use_count: int = 1,
    ):
        self.min_age_days = (
            settings.memory_retention_min_age_days
            if min_age_days is None else min_age_days
        )
        self.inactivity_days = (
            settings.memory_retention_inactivity_days
            if inactivity_days is None else inactivity_days
        )
        self.max_use_count = max_use_count

        if self.min_age_days < 1 or self.inactivity_days < 1:
            raise ValueError("Retention periods must be positive.")

        if self.max_use_count < 0:
            raise ValueError("Maximum use count cannot be negative.")

    def assess(
        self,
        record: EpisodicMemoryRecord,
        *,
        now: datetime | None = None,
    ) -> RetentionAssessment:
        if not isinstance(record, EpisodicMemoryRecord):
            raise TypeError("Expected an EpisodicMemoryRecord.")

        current_time = now or datetime.now(timezone.utc)

        if current_time.tzinfo is None:
            raise ValueError("Assessment time must be timezone-aware.")

        reasons = []

        if record.lifecycle_status != MemoryLifecycleStatus.ACTIVE:
            reasons.append("Memory is not active.")

        if record.is_protected:
            reasons.append("Memory is explicitly protected.")

        if record.status == MemoryStatus.FAILED:
            reasons.append("Failed memories are protected.")

        if record.sensitivity in self.PROTECTED_SENSITIVITIES:
            reasons.append(
                f"Sensitivity '{record.sensitivity.value}' is protected."
            )

        if not record.usage_tracked:
            reasons.append("Usage history is unknown.")

        if record.use_count > self.max_use_count:
            reasons.append("Memory usage exceeds the low-usage threshold.")

        if record.completed_at.tzinfo is None:
            reasons.append("Memory completion timestamp is not timezone-aware.")
        elif record.completed_at > current_time:
            reasons.append("Memory completion timestamp is in the future.")
        elif current_time - record.completed_at < timedelta(
            days=self.min_age_days
        ):
            reasons.append("Memory has not reached the minimum age.")

        last_activity = record.last_used_at or record.completed_at

        if last_activity.tzinfo is None:
            reasons.append("Memory activity timestamp is not timezone-aware.")
        elif last_activity > current_time:
            reasons.append("Memory activity timestamp is in the future.")
        elif current_time - last_activity < timedelta(
            days=self.inactivity_days
        ):
            reasons.append("Memory has not reached the inactivity threshold.")

        return RetentionAssessment(
            eligible=not reasons,
            reasons=tuple(reasons) if reasons else (
                "Memory meets all archival eligibility conditions.",
            ),
        )
