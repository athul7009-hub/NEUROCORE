
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlite3

from app.memory.database import SQLiteDatabase
from app.memory.meta_conflict_schemas import (
    MetaMemoryConflictRecord,
    MetaMemoryConflictStatus,
    MetaMemoryConflictType,
)
from app.memory.repositories.meta_conflict import (
    MetaMemoryConflictRepository,
)


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "meta_conflict.db")
    database.initialize()

    repo = MetaMemoryConflictRepository(database)
    repo.initialize()

    return repo


@pytest.fixture
def valid_record():
    return MetaMemoryConflictRecord(
        memory_type_a="episodic",
        memory_id_a=str(uuid4()),
        memory_type_b="semantic",
        memory_id_b=str(uuid4()),
        conflict_type=MetaMemoryConflictType.FACTUAL,
        confidence_score=0.85,
        rationale="The memories contain contradictory facts.",
    )


def test_save_and_get_record(repository, valid_record):
    repository.save(valid_record)

    assert repository.get(valid_record.conflict_id) == valid_record


def test_get_missing_record_returns_none(repository):
    assert repository.get(uuid4()) is None


def test_get_rejects_invalid_id(repository):
    with pytest.raises(TypeError):
        repository.get("invalid")


def test_duplicate_conflict_id_is_rejected(repository, valid_record):
    repository.save(valid_record)

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(valid_record)


def test_save_rejects_invalid_record(repository):
    with pytest.raises(TypeError):
        repository.save("invalid")


def test_search_returns_all_records(repository, valid_record):
    second = valid_record.model_copy(
        update={"conflict_id": uuid4()}
    )

    repository.save(valid_record)
    repository.save(second)

    assert len(repository.search()) == 2


def test_search_filters_by_status(repository, valid_record):
    repository.save(valid_record)

    confirmed = valid_record.model_copy(
        update={
            "conflict_id": uuid4(),
            "status": MetaMemoryConflictStatus.CONFIRMED,
            "reviewed_at": datetime.now(timezone.utc),
        }
    )
    repository.save(confirmed)

    results = repository.search(
        status=MetaMemoryConflictStatus.CONFIRMED,
    )

    assert results == [confirmed]


def test_search_filters_by_conflict_type(repository, valid_record):
    repository.save(valid_record)

    procedural = valid_record.model_copy(
        update={
            "conflict_id": uuid4(),
            "conflict_type": MetaMemoryConflictType.PROCEDURAL,
        }
    )
    repository.save(procedural)

    results = repository.search(
        conflict_type=MetaMemoryConflictType.PROCEDURAL,
    )

    assert results == [procedural]


def test_search_supports_combined_filters(repository, valid_record):
    repository.save(valid_record)

    confirmed = valid_record.model_copy(
        update={
            "conflict_id": uuid4(),
            "conflict_type": MetaMemoryConflictType.TEMPORAL,
            "status": MetaMemoryConflictStatus.CONFIRMED,
            "reviewed_at": datetime.now(timezone.utc),
        }
    )
    repository.save(confirmed)

    results = repository.search(
        status=MetaMemoryConflictStatus.CONFIRMED,
        conflict_type=MetaMemoryConflictType.TEMPORAL,
    )

    assert results == [confirmed]


def test_search_supports_pagination(repository, valid_record):
    records = [
        valid_record.model_copy(
            update={
                "conflict_id": uuid4(),
                "memory_id_a": str(uuid4()),
                "memory_id_b": str(uuid4()),
            }
        )
        for _ in range(3)
    ]

    for record in records:
        repository.save(record)

    assert len(repository.search(limit=2, offset=1)) == 2


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_search_rejects_invalid_limit(repository, limit):
    with pytest.raises(ValueError):
        repository.search(limit=limit)


def test_search_rejects_boolean_limit(repository):
    with pytest.raises(TypeError):
        repository.search(limit=True)


def test_search_rejects_negative_offset(repository):
    with pytest.raises(ValueError):
        repository.search(offset=-1)


def test_search_rejects_invalid_status(repository):
    with pytest.raises(TypeError):
        repository.search(status="unknown")


def test_search_rejects_invalid_conflict_type(repository):
    with pytest.raises(TypeError):
        repository.search(conflict_type="unknown")


def test_update_existing_record(repository, valid_record):
    repository.save(valid_record)

    now = datetime.now(timezone.utc)

    updated = valid_record.model_copy(
        update={
            "confidence_score": 0.95,
            "rationale": "The conflict has been reviewed.",
            "status": MetaMemoryConflictStatus.CONFIRMED,
            "reviewed_at": now,
            "updated_at": now,
        }
    )

    assert repository.update(updated)

    result = repository.get(valid_record.conflict_id)

    assert result.confidence_score == 0.95
    assert result.rationale == "The conflict has been reviewed."
    assert result.status == MetaMemoryConflictStatus.CONFIRMED
    assert result.reviewed_at == now


def test_update_does_not_change_memory_identity(
    repository,
    valid_record,
):
    repository.save(valid_record)

    updated = valid_record.model_copy(
        update={
            "memory_id_a": str(uuid4()),
            "memory_type_a": "procedural",
        }
    )

    assert repository.update(updated)

    result = repository.get(valid_record.conflict_id)

    assert result.memory_id_a == valid_record.memory_id_a
    assert result.memory_type_a == valid_record.memory_type_a


def test_update_returns_false_for_missing_record(
    repository,
    valid_record,
):
    assert not repository.update(valid_record)


def test_update_rejects_invalid_record(repository):
    with pytest.raises(TypeError):
        repository.update("invalid")


def test_records_survive_repository_recreation(tmp_path, valid_record):
    database_path = tmp_path / "meta_conflict.db"

    database = SQLiteDatabase(database_path)
    database.initialize()

    first_repository = MetaMemoryConflictRepository(database)
    first_repository.initialize()
    first_repository.save(valid_record)

    second_repository = MetaMemoryConflictRepository(
        SQLiteDatabase(database_path)
    )

    assert second_repository.get(valid_record.conflict_id) == valid_record


def test_initialize_is_idempotent(repository):
    repository.initialize()
    repository.initialize()

    assert repository.search() == []
def test_transition_status_succeeds_for_expected_status(
    repository,
    valid_record,
):
    repository.save(valid_record)

    reviewed_at = datetime.now(timezone.utc)

    assert repository.transition_status(
        valid_record.conflict_id,
        expected_status=MetaMemoryConflictStatus.DETECTED,
        new_status=MetaMemoryConflictStatus.CONFIRMED,
        reviewed_at=reviewed_at,
    )

    result = repository.get(valid_record.conflict_id)

    assert result.status == MetaMemoryConflictStatus.CONFIRMED
    assert result.reviewed_at == reviewed_at


def test_transition_status_rejects_stale_status(
    repository,
    valid_record,
):
    repository.save(valid_record)

    reviewed_at = datetime.now(timezone.utc)

    assert repository.transition_status(
        valid_record.conflict_id,
        expected_status=MetaMemoryConflictStatus.DETECTED,
        new_status=MetaMemoryConflictStatus.CONFIRMED,
        reviewed_at=reviewed_at,
    )

    assert not repository.transition_status(
        valid_record.conflict_id,
        expected_status=MetaMemoryConflictStatus.DETECTED,
        new_status=MetaMemoryConflictStatus.DISMISSED,
        reviewed_at=reviewed_at,
    )


def test_transition_status_rejects_invalid_lifecycle_transition(
    repository,
    valid_record,
):
    repository.save(valid_record)

    with pytest.raises(ValueError):
        repository.transition_status(
            valid_record.conflict_id,
            expected_status=MetaMemoryConflictStatus.DETECTED,
            new_status=MetaMemoryConflictStatus.RESOLVED,
            reviewed_at=datetime.now(timezone.utc),
        )


def test_transition_status_does_not_change_memory_identity(
    repository,
    valid_record,
):
    repository.save(valid_record)

    repository.transition_status(
        valid_record.conflict_id,
        expected_status=MetaMemoryConflictStatus.DETECTED,
        new_status=MetaMemoryConflictStatus.CONFIRMED,
        reviewed_at=datetime.now(timezone.utc),
    )

    result = repository.get(valid_record.conflict_id)

    assert result.memory_type_a == valid_record.memory_type_a
    assert result.memory_id_a == valid_record.memory_id_a
    assert result.memory_type_b == valid_record.memory_type_b
    assert result.memory_id_b == valid_record.memory_id_b