
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)


@pytest.fixture
def valid_meta_memory():
    return MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=str(uuid4()),
    )


def test_create_valid_meta_memory(valid_meta_memory):
    assert valid_meta_memory.memory_type == MetaMemoryType.EPISODIC
    assert valid_meta_memory.usage_count == 0
    assert valid_meta_memory.quality_score is None
    assert valid_meta_memory.assessment_confidence is None
    assert valid_meta_memory.last_assessed_at is None
    assert (
        valid_meta_memory.staleness_status
        == MetaMemoryStalenessStatus.UNKNOWN
    )


def test_meta_id_is_generated(valid_meta_memory):
    assert valid_meta_memory.meta_id is not None


def test_all_memory_types_are_supported():
    for memory_type in MetaMemoryType:
        record = MetaMemoryRecord(
            memory_type=memory_type,
            memory_id=str(uuid4()),
        )
        assert record.memory_type == memory_type


def test_memory_id_cannot_be_blank():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id="   ",
        )


def test_memory_id_cannot_exceed_maximum_length():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id="a" * 101,
        )


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_quality_score_must_be_between_zero_and_one(score):
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            quality_score=score,
            assessment_confidence=0.8,
            last_assessed_at=datetime.now(timezone.utc),
        )


@pytest.mark.parametrize(
    "confidence",
    [-0.1, 1.1],
)
def test_assessment_confidence_must_be_between_zero_and_one(
    confidence,
):
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            quality_score=0.8,
            assessment_confidence=confidence,
            last_assessed_at=datetime.now(timezone.utc),
        )


def test_negative_usage_count_is_rejected():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            usage_count=-1,
        )


def test_default_usage_count_is_zero(valid_meta_memory):
    assert valid_meta_memory.usage_count == 0


def test_assessment_fields_can_be_set_together():
    now = datetime.now(timezone.utc)

    record = MetaMemoryRecord(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=str(uuid4()),
        quality_score=0.85,
        assessment_confidence=0.9,
        last_assessed_at=now,
    )

    assert record.quality_score == 0.85
    assert record.assessment_confidence == 0.9
    assert record.last_assessed_at == now


@pytest.mark.parametrize(
    "assessment_data",
    [
        {"quality_score": 0.8},
        {"assessment_confidence": 0.8},
        {"last_assessed_at": datetime.now(timezone.utc)},
        {
            "quality_score": 0.8,
            "assessment_confidence": 0.9,
        },
        {
            "quality_score": 0.8,
            "last_assessed_at": datetime.now(timezone.utc),
        },

    ],
)
def test_partial_assessment_data_is_rejected(assessment_data):
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            **assessment_data,
        )


def test_updated_at_cannot_precede_created_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            created_at=now,
            updated_at=now - timedelta(seconds=1),
        )


def test_naive_created_at_is_rejected():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            created_at=datetime.now(),
        )


def test_naive_last_retrieved_at_is_rejected():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            last_retrieved_at=datetime.now(),
        )


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
            arbitrary_field="not allowed",
        )


def test_default_timestamps_are_timezone_aware(valid_meta_memory):
    assert valid_meta_memory.created_at.tzinfo is not None
    assert valid_meta_memory.updated_at.tzinfo is not None


def test_staleness_status_can_be_changed():
    record = MetaMemoryRecord(
        memory_type=MetaMemoryType.PROCEDURAL,
        memory_id=str(uuid4()),
        staleness_status=(
            MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
        ),
    )

    assert (
        record.staleness_status
        == MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
    )


def test_inconclusive_assessment_data_is_valid():
    record = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id="memory-inconclusive",
        quality_score=None,
        assessment_confidence=0.0,
        last_assessed_at=datetime.now(timezone.utc),
    )

    assert record.quality_score is None
    assert record.assessment_confidence == 0.0
    assert record.last_assessed_at is not None
