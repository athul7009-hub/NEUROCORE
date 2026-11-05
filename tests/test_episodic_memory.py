
import sqlite3
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import EpisodicMemoryRecord, MemoryStatus


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "memory.db")
    database.initialize()

    repo = EpisodicMemoryRepository(database)
    repo.initialize()

    return repo


def create_record():
    now = datetime.now(timezone.utc)

    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Analyzed a project folder.",
        created_at=now,
    )


def test_save_and_retrieve_memory(repository):
    record = create_record()

    repository.save(record)
    retrieved = repository.get(record.task_id)

    assert retrieved == record


def test_missing_memory_returns_none(repository):
    assert repository.get(uuid4()) is None


def test_duplicate_task_id_is_rejected(repository):
    record = create_record()

    repository.save(record)

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(record)


def test_recent_memories(repository):
    first = create_record()
    second = create_record()

    repository.save(first)
    repository.save(second)

    recent = repository.get_recent(limit=2)

    assert len(recent) == 2
    assert recent[0].task_id == second.task_id


def test_recent_memory_rejects_invalid_limit(repository):
    with pytest.raises(ValueError, match="Limit must be positive"):
        repository.get_recent(limit=0)
