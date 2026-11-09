
from datetime import datetime, timedelta, timezone

from app.memory.meta_maintenance_schemas import (
    MetaMemoryMaintenanceReport,
)
from app.memory.meta_manager import MetaMemoryManager


class MetaMemoryMaintenanceManager:
    """Coordinates bounded maintenance of meta-memory assessments."""

    DEFAULT_BATCH_SIZE = 20
    MAX_BATCH_SIZE = 100
    MAX_RECORDS_PER_RUN = 100

    def __init__(self, meta_manager: MetaMemoryManager) -> None:
        if not isinstance(meta_manager, MetaMemoryManager):
            raise TypeError("Expected a MetaMemoryManager.")

        self.meta_manager = meta_manager

    def maintain(
        self,
        *,
        requesting_agent: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        now: datetime | None = None,
    ) -> MetaMemoryMaintenanceReport:
        """Assesses metadata records requiring initial or renewed assessment."""

        if isinstance(batch_size, bool) or not isinstance(batch_size, int):
            raise TypeError("batch_size must be an integer.")

        if not 1 <= batch_size <= self.MAX_BATCH_SIZE:
            raise ValueError(
                f"batch_size must be between 1 and {self.MAX_BATCH_SIZE}."
            )

        # Enforce coordinator-only authorization before accessing records.
        self.meta_manager.authorize_maintenance(requesting_agent)

        started_at = datetime.now(timezone.utc)

        if now is not None:
            if not isinstance(now, datetime):
                raise TypeError("now must be a datetime or None.")

            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("now must be timezone-aware.")

            now = now.astimezone(timezone.utc)

            if now > started_at:
                raise ValueError("now cannot be in the future.")

            assessment_time = now
        else:
            assessment_time = started_at

        assessed = 0
        skipped = 0
        failed_meta_ids = []
        total_examined = 0
        offset = 0

        stale_after = timedelta(
            days=self.meta_manager.assessment_engine.STALE_AFTER_DAYS
        )

        while total_examined < self.MAX_RECORDS_PER_RUN:
            current_batch_size = min(
                batch_size,
                self.MAX_RECORDS_PER_RUN - total_examined,
            )

            records = self.meta_manager.search(
                requesting_agent=requesting_agent,
                limit=current_batch_size,
                offset=offset,
            )

            if not records:
                break

            total_examined += len(records)
            offset += current_batch_size

            for record in records:
                needs_assessment = (
                    record.last_assessed_at is None
                    or assessment_time - record.last_assessed_at >= stale_after
                )

                if not needs_assessment:
                    skipped += 1
                    continue

                try:
                    result = self.meta_manager.assess_and_persist(
                        record.meta_id,
                        requesting_agent=requesting_agent,
                        now=assessment_time,
                    )

                    if result is None:
                        failed_meta_ids.append(record.meta_id)
                    else:
                        assessed += 1

                except Exception:
                    # One record failure must not stop the remaining batch.
                    failed_meta_ids.append(record.meta_id)

            if len(records) < current_batch_size:
                break

        completed_at = datetime.now(timezone.utc)

        return MetaMemoryMaintenanceReport(
            total_examined=total_examined,
            assessed=assessed,
            skipped=skipped,
            failed=len(failed_meta_ids),
            failed_meta_ids=failed_meta_ids,
            started_at=started_at,
            completed_at=completed_at,
        )
