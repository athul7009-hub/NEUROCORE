
from datetime import datetime, timedelta, timezone

from app.memory.meta_assessment_schemas import MetaMemoryAssessment
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
)


class MetaMemoryAssessmentEngine:
    """Produces advisory assessments using meta-memory metadata only."""

    STALE_AFTER_DAYS = 90
    RECENCY_WINDOW_DAYS = 180
    USAGE_SCORE_LIMIT = 10
    CONFIDENCE_USAGE_LIMIT = 5

    def assess(
        self,
        record: MetaMemoryRecord,
        *,
        now: datetime | None = None,
    ) -> MetaMemoryAssessment:
        """Assesses memory quality, evidence confidence, and staleness."""

        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("Expected a MetaMemoryRecord.")

        if now is not None and not isinstance(now, datetime):
            raise TypeError("now must be a datetime.")

        assessed_at = (
            now if now is not None
            else datetime.now(timezone.utc)
        )

        if (
            assessed_at.tzinfo is None
            or assessed_at.utcoffset() is None
        ):
            raise ValueError("Assessment timestamp must be timezone-aware.")

        if assessed_at > datetime.now(timezone.utc):
            raise ValueError("Assessment timestamp cannot be in the future.")

        for timestamp in (
            record.created_at,
            record.last_retrieved_at,
        ):
            if timestamp is not None and timestamp > assessed_at:
                raise ValueError("Memory activity cannot be in the future.")

        last_activity = record.last_retrieved_at or record.created_at
        age = assessed_at - last_activity

        stale = age >= timedelta(days=self.STALE_AFTER_DAYS)

        staleness_status = (
            MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
            if stale
            else MetaMemoryStalenessStatus.CURRENT
        )

        if record.usage_count == 0:
            return MetaMemoryAssessment(
                quality_score=None,
                assessment_confidence=0.0,
                staleness_status=staleness_status,
                assessed_at=assessed_at,
                rationale=(
                    "No retrieval evidence is available; "
                    "quality cannot be estimated. "
                    + (
                        "The memory has not been retrieved for at least "
                        f"{self.STALE_AFTER_DAYS} days."
                        if stale
                        else "There is insufficient evidence to recommend review."
                    )
                ),
            )

        usage_score = min(
            record.usage_count / self.USAGE_SCORE_LIMIT,
            1.0,
        )

        recency_score = max(
            0.0,
            1.0 - (
                age.total_seconds()
                / (self.RECENCY_WINDOW_DAYS * 86400)
            ),
        )

        quality_score = (
            usage_score * 0.5
            + recency_score * 0.5
        )

        assessment_confidence = min(
            record.usage_count / self.CONFIDENCE_USAGE_LIMIT,
            1.0,
        )

        rationale = (
            f"Based on {record.usage_count} recorded retrievals "
            f"and {age.days} days since the last retrieval "
            f"or creation."
        )

        if stale:
            rationale += (
                f" Review is recommended because activity is at least "
                f"{self.STALE_AFTER_DAYS} days old."
            )
        else:
            rationale += " Recent activity does not currently indicate staleness."

        return MetaMemoryAssessment(
            quality_score=round(quality_score, 4),
            assessment_confidence=round(assessment_confidence, 4),
            staleness_status=staleness_status,
            assessed_at=assessed_at,
            rationale=rationale,
        )
