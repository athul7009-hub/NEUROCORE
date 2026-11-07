
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.schemas import MemorySensitivity
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


def create_record(**overrides):
    data = {
        "subject": "Python",
        "predicate": "is_a",
        "object": "Programming Language",
        "source": SemanticMemorySource.DOCUMENT,
    }
    data.update(overrides)
    return SemanticMemoryRecord(**data)


def test_valid_semantic_memory_record():
    record = create_record()

    assert record.subject == "Python"
    assert record.predicate == "is_a"
    assert record.object == "Programming Language"


def test_new_memory_defaults_to_candidate():
    record = create_record()

    assert record.status == SemanticMemoryStatus.CANDIDATE


def test_new_memory_has_unique_id():
    first = create_record()
    second = create_record()

    assert first.memory_id != second.memory_id


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        create_record(confidence=1.5)

    with pytest.raises(ValidationError):
        create_record(confidence=-0.1)


def test_confidence_accepts_boundary_values():
    assert create_record(confidence=0.0).confidence == 0.0
    assert create_record(confidence=1.0).confidence == 1.0


def test_validated_memory_requires_validation_metadata():
    with pytest.raises(ValidationError):
        create_record(status=SemanticMemoryStatus.VALIDATED)


def test_validated_memory_accepts_validation_metadata():
    timestamp = datetime.now(timezone.utc)

    record = create_record(
        status=SemanticMemoryStatus.VALIDATED,
        validated_at=timestamp,
        validated_by="CoordinatorAgent",
    )

    assert record.validated_at == timestamp
    assert record.validated_by == "CoordinatorAgent"


def test_candidate_cannot_have_validation_metadata():
    with pytest.raises(ValidationError):
        create_record(
            validated_at=datetime.now(timezone.utc),
            validated_by="CoordinatorAgent",
        )


def test_semantic_memory_supports_episodic_provenance():
    task_id = uuid4()

    record = create_record(
        source=SemanticMemorySource.EPISODIC,
        source_task_id=task_id,
    )

    assert record.source_task_id == task_id


def test_semantic_memory_defaults_to_internal_sensitivity():
    record = create_record()

    assert record.sensitivity == MemorySensitivity.INTERNAL


def test_semantic_memory_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        create_record(unexpected_field="invalid")
