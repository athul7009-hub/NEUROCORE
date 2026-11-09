
from uuid import uuid4

import pytest
from datetime import datetime, timezone
from app.memory.database import SQLiteDatabase
from app.memory.manager import MemoryManager
from app.memory.memory_policy import MemoryPolicy
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
)


@pytest.fixture
def memory_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "episodic_identity.db")
    database.initialize()

    repository = EpisodicMemoryRepository(database)
    repository.initialize()

    return MemoryManager(repository, MemoryPolicy())


def create_record(task_id):
    now = datetime.now(timezone.utc)

    return EpisodicMemoryRecord(
        task_id=task_id,
        intent="PLAN_TASK",
        status="completed",
        agent_name="PlanningAgent",
        summary="Private memory content",
        created_at=now,
        completed_at=now,
    )

def test_inspect_active_identity(memory_manager):
    task_id = uuid4()
    memory_manager.repository.save(create_record(task_id))

    result = memory_manager.inspect_identity(
        task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == MemoryLifecycleStatus.ACTIVE
    assert not isinstance(result, EpisodicMemoryRecord)


def test_inspect_archived_identity(memory_manager):
    task_id = uuid4()
    record = create_record(task_id)
    memory_manager.repository.save(record)

    stored_record = memory_manager.repository.get(task_id)

    assert stored_record is not None

    assert memory_manager.repository.archive(
        task_id,
        expected_record=stored_record,
    ) is True

    result = memory_manager.inspect_identity(
        task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == MemoryLifecycleStatus.ARCHIVED


def test_inspect_nonexistent_identity(memory_manager):
    result = memory_manager.inspect_identity(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    )

    assert result is None


def test_non_coordinator_cannot_inspect_identity(memory_manager):
    with pytest.raises(PermissionError):
        memory_manager.inspect_identity(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_invalid_task_id_is_rejected(memory_manager):
    with pytest.raises(TypeError):
        memory_manager.inspect_identity(
            "invalid",
            requesting_agent="CoordinatorAgent",
        )
