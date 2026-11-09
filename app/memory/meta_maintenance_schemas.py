
from datetime import datetime, timezone
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class MetaMemoryMaintenanceReport(BaseModel):
    """Summary of a meta-memory maintenance run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    total_examined: int = Field(ge=0)
    assessed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    failed: int = Field(ge=0)

    failed_meta_ids: list[UUID] = Field(default_factory=list)

    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def validate_report(self):
        if self.total_examined != self.assessed + self.skipped + self.failed:
            raise ValueError(
                "total_examined must equal assessed + skipped + failed."
            )

        if self.failed != len(self.failed_meta_ids):
            raise ValueError(
                "failed must match the number of failed metadata IDs."
            )

        if self.started_at.tzinfo is None or self.started_at.utcoffset() is None:
            raise ValueError("started_at must be timezone-aware.")

        if (
            self.completed_at.tzinfo is None
            or self.completed_at.utcoffset() is None
        ):
            raise ValueError("completed_at must be timezone-aware.")

        if self.completed_at < self.started_at:
            raise ValueError("completed_at cannot precede started_at.")

        return self
