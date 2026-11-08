
from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlite3

from app.memory.database import SQLiteDatabase
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)
from app.memory.repositories.meta_memory import MetaMemoryRepository


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "meta_memory.db")
    database.initialize()

    repo = MetaMemoryRepository(database)
    repo.initialize()

    return repo


@pytest.fixture
def valid_record():
    return MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=str(uuid4()),
    )


def test_save_and_get_record(repository, valid_record):
    repository.save(valid_record)

    result = repository.get(valid_record.meta_id)

    assert result == valid_record


def test_get_missing_record_returns_none(repository):
    assert repository.get(uuid4()) is None


def test_get_rejects_invalid_id(repository):
    with pytest.raises(TypeError):
        repository.get("invalid")


def test_duplicate_memory_identity_is_rejected(
    repository,
    valid_record,
):
    repository.save(valid_record)

    duplicate = MetaMemoryRecord(
        memory_type=valid_record.memory_type,
        memory_id=valid_record.memory_id,
    )

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(duplicate)


def test_same_memory_id_can_exist_for_different_types(repository):
    memory_id = str(uuid4())

    episodic = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=memory_id,
    )

    semantic = MetaMemoryRecord(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=memory_id,
    )

    repository.save(episodic)
    repository.save(semantic)

    assert repository.get_for_memory(
        MetaMemoryType.EPISODIC,
        memory_id,
    ) == episodic

    assert repository.get_for_memory(
        MetaMemoryType.SEMANTIC,
        memory_id,
    ) == semantic


def test_get_for_memory_returns_none(repository):
    result = repository.get_for_memory(
        MetaMemoryType.EPISODIC,
        str(uuid4()),
    )

    assert result is None


def test_get_for_memory_rejects_invalid_type(repository):
    with pytest.raises(TypeError):
        repository.get_for_memory("episodic", str(uuid4()))


def test_get_for_memory_rejects_blank_id(repository):
    with pytest.raises(ValueError):
        repository.get_for_memory(
            MetaMemoryType.EPISODIC,
            " ",
        )


def test_search_returns_all_records(repository):
    records = [
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
        ),
        MetaMemoryRecord(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=str(uuid4()),
        ),
    ]

    for record in records:
        repository.save(record)

    results = repository.search()

    assert len(results) == 2


def test_search_filters_by_memory_type(repository):
    episodic = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=str(uuid4()),
    )

    semantic = MetaMemoryRecord(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=str(uuid4()),
    )

    repository.save(episodic)
    repository.save(semantic)

    results = repository.search(
        memory_type=MetaMemoryType.EPISODIC,
    )

    assert results == [episodic]


def test_search_filters_by_staleness(repository):
    current = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=str(uuid4()),
    )

    review = MetaMemoryRecord(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=str(uuid4()),
        staleness_status=(
            MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
        ),
    )

    repository.save(current)
    repository.save(review)

    results = repository.search(
        staleness_status=(
            MetaMemoryStalenessStatus.REVIEW_RECOMMENDED
        ),
    )

    assert results == [review]


def test_search_supports_pagination(repository):
    records = [
        MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=str(uuid4()),
        )
        for _ in range(3)
    ]

    for record in records:
        repository.save(record)

    results = repository.search(limit=2, offset=1)

    assert len(results) == 2


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


def test_search_rejects_invalid_memory_type(repository):
    with pytest.raises(TypeError):
        repository.search(memory_type="episodic")


def test_search_rejects_invalid_staleness(repository):
    with pytest.raises(TypeError):
        repository.search(staleness_status="unknown")


def test_update_existing_record(repository, valid_record):
    repository.save(valid_record)

    now = datetime.now(timezone.utc)

    updated = valid_record.model_copy(
        update={
            "quality_score": 0.85,
            "assessment_confidence": 0.9,
            "last_assessed_at": now,
            "staleness_status": MetaMemoryStalenessStatus.CURRENT,
            "updated_at": now,
        }
    )

    assert repository.update(updated)

    result = repository.get(valid_record.meta_id)

    assert result.quality_score == 0.85
    assert result.assessment_confidence == 0.9
    assert result.staleness_status == MetaMemoryStalenessStatus.CURRENT


def test_update_does_not_change_memory_identity(
    repository,
    valid_record,
):
    repository.save(valid_record)

    updated = valid_record.model_copy(
        update={
            "memory_id": str(uuid4()),
            "memory_type": MetaMemoryType.SEMANTIC,
        }
    )

    assert not repository.update(updated)

    result = repository.get(valid_record.meta_id)

    assert result.memory_id == valid_record.memory_id
    assert result.memory_type == valid_record.memory_type


def test_update_returns_false_for_missing_record(
    repository,
    valid_record,
):
    assert not repository.update(valid_record)


def test_update_rejects_invalid_record(repository):
    with pytest.raises(TypeError):
        repository.update("invalid")


def test_record_usage_increments_count(repository, valid_record):
    repository.save(valid_record)

    assert repository.record_usage(
        valid_record.memory_type,
        valid_record.memory_id,
    )

    result = repository.get(valid_record.meta_id)

    assert result.usage_count == 1
    assert result.last_retrieved_at is not None


def test_record_usage_increments_multiple_times(
    repository,
    valid_record,
):
    repository.save(valid_record)

    for _ in range(3):
        assert repository.record_usage(
            valid_record.memory_type,
            valid_record.memory_id,
        )

    result = repository.get(valid_record.meta_id)

    assert result.usage_count == 3


def test_record_usage_uses_supplied_timestamp(
    repository,
    valid_record,
):
    repository.save(valid_record)

    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    repository.record_usage(
        valid_record.memory_type,
        valid_record.memory_id,
        retrieved_at=retrieved_at,
    )

    result = repository.get(valid_record.meta_id)

    assert result.last_retrieved_at == retrieved_at


def test_record_usage_returns_false_for_missing_metadata(repository):
    assert not repository.record_usage(
        MetaMemoryType.EPISODIC,
        str(uuid4()),
    )


def test_record_usage_rejects_naive_timestamp(
    repository,
    valid_record,
):
    repository.save(valid_record)

    with pytest.raises(ValueError):
        repository.record_usage(
            valid_record.memory_type,
            valid_record.memory_id,
            retrieved_at=datetime.now(),
        )


def test_record_usage_rejects_invalid_type(repository):
    with pytest.raises(TypeError):
        repository.record_usage("episodic", str(uuid4()))


def test_record_usage_rejects_blank_memory_id(repository):
    with pytest.raises(ValueError):
        repository.record_usage(
            MetaMemoryType.EPISODIC,
            " ",
        )


def test_initialize_is_idempotent(repository):
    repository.initialize()
    repository.initialize()

    assert repository.search() == []
