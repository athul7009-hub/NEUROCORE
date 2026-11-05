
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.manager import MemoryManager
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()
    return memory_manager


def create_record():
    now = datetime.now(timezone.utc)

    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Successfully analyzed project files.",
        created_at=now,
        completed_at=now,
    )


def test_remember_and_retrieve_task(manager):
    record = create_record()

    manager.remember_task(record)

    assert manager.get_task(record.task_id) == record


def test_missing_task_returns_none(manager):
    assert manager.get_task(uuid4()) is None


def test_get_recent_tasks(manager):
    first = create_record()
    second = create_record()

    manager.remember_task(first)
    manager.remember_task(second)

    recent = manager.get_recent_tasks(limit=2)

    assert len(recent) == 2
    assert recent[0].task_id == second.task_id


def test_invalid_record_is_rejected(manager):
    with pytest.raises(TypeError):
        manager.remember_task({"summary": "Invalid memory"})


def test_initialize_is_safe_to_repeat(manager):
    manager.initialize()
    manager.initialize()
