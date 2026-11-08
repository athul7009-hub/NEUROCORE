
from datetime import datetime, timedelta, timezone

import pytest

from app.memory.meta_assessment import MetaMemoryAssessmentEngine
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)


@pytest.fixture
def engine():
    return MetaMemoryAssessmentEngine()


@pytest.fixture
def now():
    return datetime(2026, 11, 8, 12, 0, tzinfo=timezone.utc)


def create_record(**overrides):
    data = {
        "memory_type": MetaMemoryType.EPISODIC,
        "memory_id": "assessment-test-memory",
        "usage_count": 5,
        "last_retrieved_at": datetime(
            2026, 11, 1, 12, 0, tzinfo=timezone.utc
        ),
        "created_at": datetime(
            2026, 10, 1, 12, 0, tzinfo=timezone.utc
        ),
        "updated_at": datetime(
            2026, 11, 1, 12, 0, tzinfo=timezone.utc
        ),
    }
    data.update(overrides)
    return MetaMemoryRecord(**data)


def test_assesses_valid_memory(engine, now):
    assessment = engine.assess(create_record(), now=now)

    assert assessment.quality_score is not None
    assert 0.0 <= assessment.quality_score <= 1.0
    assert assessment.assessment_confidence == 1.0
    assert assessment.staleness_status == MetaMemoryStalenessStatus.CURRENT


def test_returns_no_quality_score_without_usage(engine, now):
    record = create_record(
        usage_count=0,
        last_retrieved_at=None,
    )

    assessment = engine.assess(record, now=now)

    assert assessment.quality_score is None
    assert assessment.assessment_confidence == 0.0


def test_usage_score_increases_with_retrieval_count(engine, now):
    low_usage = engine.assess(
        create_record(usage_count=2),
        now=now,
    )
    high_usage = engine.assess(
        create_record(usage_count=8),
        now=now,
    )

    assert high_usage.quality_score > low_usage.quality_score


def test_usage_score_is_capped(engine, now):
    assessment = engine.assess(
        create_record(usage_count=100),
        now=now,
    )

    assert assessment.assessment_confidence == 1.0


def test_confidence_increases_with_usage(engine, now):
    low = engine.assess(
        create_record(usage_count=1),
        now=now,
    )
    high = engine.assess(
        create_record(usage_count=4),
        now=now,
    )

    assert high.assessment_confidence > low.assessment_confidence


def test_confidence_is_capped_at_one(engine, now):
    assessment = engine.assess(
        create_record(usage_count=20),
        now=now,
    )

    assert assessment.assessment_confidence == 1.0


def test_recent_retrieval_produces_higher_quality(engine, now):
    recent = engine.assess(
        create_record(
            last_retrieved_at=now - timedelta(days=1)
        ),
        now=now,
    )
    older = engine.assess(
        create_record(
            last_retrieved_at=now - timedelta(days=60)
        ),
        now=now,
    )

    assert recent.quality_score > older.quality_score


def test_stale_memory_recommends_review(engine, now):
    record = create_record(
        last_retrieved_at=now - timedelta(days=91)
    )

    assessment = engine.assess(record, now=now)

    assert (
        assessment.staleness_status
        == MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
    )


def test_memory_at_staleness_boundary_recommends_review(engine, now):
    record = create_record(
        last_retrieved_at=now - timedelta(days=90)
    )

    assessment = engine.assess(record, now=now)

    assert (
        assessment.staleness_status
        == MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
    )


def test_memory_before_staleness_boundary_is_current(engine, now):
    record = create_record(
        last_retrieved_at=now - timedelta(days=89)
    )

    assessment = engine.assess(record, now=now)

    assert assessment.staleness_status == MetaMemoryStalenessStatus.CURRENT


def test_uses_creation_time_when_never_retrieved(engine, now):
    record = create_record(
        usage_count=0,
        last_retrieved_at=None,
        created_at=now - timedelta(days=100),
        updated_at=now - timedelta(days=100),
    )

    assessment = engine.assess(record, now=now)

    assert (
        assessment.staleness_status
        == MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
    )


def test_future_activity_does_not_produce_negative_age(engine, now):
    record = create_record(
        last_retrieved_at=now + timedelta(days=10)
    )

    assessment = engine.assess(record, now=now)

    assert assessment.quality_score == 0.75
    assert assessment.staleness_status == MetaMemoryStalenessStatus.CURRENT


def test_rejects_invalid_record(engine):
    with pytest.raises(TypeError):
        engine.assess("invalid")


def test_rejects_naive_assessment_time(engine):
    with pytest.raises(ValueError):
        engine.assess(
            create_record(),
            now=datetime(2026, 11, 8, 12, 0),
        )


def test_assessment_does_not_modify_original_record(engine, now):
    record = create_record()
    original = record.model_dump()

    engine.assess(record, now=now)

    assert record.model_dump() == original


def test_assessment_contains_rationale(engine, now):
    assessment = engine.assess(create_record(), now=now)

    assert assessment.rationale.strip()
    assert "5 recorded retrievals" in assessment.rationale


def test_assessment_uses_supplied_timestamp(engine, now):
    assessment = engine.assess(create_record(), now=now)

    assert assessment.assessed_at == now
