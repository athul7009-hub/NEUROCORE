from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.memory.meta_conflict_schemas import (
    MetaMemoryConflictRecord,
    MetaMemoryConflictStatus,
    MetaMemoryConflictType,
)


def create_conflict(**overrides):
    data = {
        "memory_type_a": "semantic",
        "memory_id_a": "memory-001",
        "memory_type_b": "episodic",
        "memory_id_b": "memory-002",
        "conflict_type": MetaMemoryConflictType.FACTUAL,
        "confidence_score": 0.85,
        "rationale": "The memories contain contradictory facts.",
    }
    data.update(overrides)
    return MetaMemoryConflictRecord(**data)


def test_creates_valid_conflict():
    conflict = create_conflict()

    assert conflict.status == MetaMemoryConflictStatus.DETECTED
    assert conflict.reviewed_at is None
    assert conflict.confidence_score == 0.85


def test_generates_unique_conflict_ids():
    first = create_conflict()
    second = create_conflict()

    assert first.conflict_id != second.conflict_id


def test_rejects_conflict_with_itself():
    with pytest.raises(ValidationError):
        create_conflict(
            memory_type_b="semantic",
            memory_id_b="memory-001",
        )


@pytest.mark.parametrize(
    "confidence",
    [-0.1, 1.1],
)
def test_rejects_invalid_confidence(confidence):
    with pytest.raises(ValidationError):
        create_conflict(confidence_score=confidence)


def test_rejects_blank_memory_type():
    with pytest.raises(ValidationError):
        create_conflict(memory_type_a="   ")


def test_rejects_blank_memory_id():
    with pytest.raises(ValidationError):
        create_conflict(memory_id_a="   ")


def test_rejects_blank_rationale():
    with pytest.raises(ValidationError):
        create_conflict(rationale="   ")


def test_strips_rationale():
    conflict = create_conflict(rationale="  Conflicting facts.  ")

    assert conflict.rationale == "Conflicting facts."


def test_rejects_naive_timestamps():
    with pytest.raises(ValidationError):
        create_conflict(
            detected_at=datetime(2026, 1, 1)
        )


def test_rejects_detected_conflict_with_reviewed_at():
    with pytest.raises(ValidationError):
        create_conflict(
            reviewed_at=datetime.now(timezone.utc)
        )


@pytest.mark.parametrize(
    "status",
    [
        MetaMemoryConflictStatus.CONFIRMED,
        MetaMemoryConflictStatus.DISMISSED,
        MetaMemoryConflictStatus.RESOLVED,
    ],
)
def test_reviewed_conflicts_require_reviewed_at(status):
    with pytest.raises(ValidationError):
        create_conflict(status=status)


def test_rejects_updated_at_before_created_at():
    with pytest.raises(ValidationError):
        create_conflict(
            created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )