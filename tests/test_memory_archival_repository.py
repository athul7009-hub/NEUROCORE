from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemoryStatus,
)


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "archival.db")
    result = EpisodicMemoryRepository(database)
    result.initialize()
    return result


def create_record():
    now = datetime.now(timezone.utc)

    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Original memory summary.",
        created_at=now - timedelta(days=120),
        completed_at=now - timedelta(days=120),
        usage_tracked=True,
    )


def test_archive_preserves_original_memory(repository):
    record = create_record()
    repository.save(record)

    assert repository.archive(record.task_id) is True

    assert repository.get(record.task_id) is None

    archived = repository.get(
        record.task_id,
        include_archived=True,
    )

    assert archived is not None
    assert archived.summary == record.summary
    assert archived.status == record.status
    assert archived.lifecycle_status == MemoryLifecycleStatus.ARCHIVED
    assert archived.archived_at is not None


def test_archive_missing_memory_returns_false(repository):
    assert repository.archive(uuid4()) is False


def test_archive_already_archived_memory_returns_false(repository):
    record = create_record()
    repository.save(record)

    assert repository.archive(record.task_id) is True
    assert repository.archive(record.task_id) is False


def test_restore_archived_memory(repository):
    record = create_record()
    repository.save(record)
    repository.archive(record.task_id)

    assert repository.restore(record.task_id) is True

    restored = repository.get(record.task_id)

    assert restored is not None
    assert restored.lifecycle_status == MemoryLifecycleStatus.ACTIVE
    assert restored.archived_at is None


def test_restore_active_memory_returns_false(repository):
    record = create_record()
    repository.save(record)

    assert repository.restore(record.task_id) is False


def test_archived_query_returns_only_archived_records(repository):
    active = create_record()
    archived = create_record()

    repository.save(active)
    repository.save(archived)
    repository.archive(archived.task_id)

    results = repository.get_archived()

    assert len(results) == 1
    assert results[0].task_id == archived.task_id


def test_archived_query_supports_filters(repository):
    first = create_record()
    second = create_record().model_copy(
        update={"intent": "code_review"}
    )

    repository.save(first)
    repository.save(second)
    repository.archive(first.task_id)
    repository.archive(second.task_id)

    results = repository.get_archived(intent="file_analysis")

    assert len(results) == 1
    assert results[0].task_id == first.task_id


@pytest.mark.parametrize("limit", [0, 101, True, 1.5, "5"])
def test_archived_query_rejects_invalid_limits(repository, limit):
    with pytest.raises((TypeError, ValueError)):
        repository.get_archived(limit=limit)