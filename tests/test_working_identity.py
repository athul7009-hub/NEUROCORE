
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.identity_schemas import (
    MemoryIdentityAvailability,
)
from app.memory.repositories.working_memory import (
    WorkingMemoryRepository,
)
from app.memory.working_manager import WorkingMemoryManager
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "working_identity.db")
    repository = WorkingMemoryRepository(database)
    instance = WorkingMemoryManager(repository)
    instance.initialize()
    return instance


def create_record(
    *,
    task_id=None,
    expires_at=None,
):
    now = datetime.now(timezone.utc)

    return WorkingMemoryRecord(
        task_id=task_id or uuid4(),
        key="project_status",
        entry_type=WorkingMemoryEntryType.TASK_STATE,
        content={"status": "in_progress"},
        source_agent="PlanningAgent",
        created_at=now - timedelta(minutes=2),
        updated_at=now - timedelta(minutes=1),
        expires_at=expires_at or now + timedelta(minutes=10),
    )


def inspect(manager, entry_id, task_id):
    return manager.inspect_identity(
        entry_id,
        task_id,
        requesting_agent="CoordinatorAgent",
    )


def test_inspect_available_entry(manager):
    record = create_record()
    manager.remember(
        record,
        requesting_agent="PlanningAgent",
    )

    result = inspect(manager, record.entry_id, record.task_id)

    assert result.exists is True
    assert result.availability == MemoryIdentityAvailability.AVAILABLE
    assert result.lifecycle_status == "active"
    assert result.memory_id == record.entry_id
    assert result.task_id == record.task_id


def test_inspect_expired_entry(manager):
    record = create_record(
        expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
    )
    manager.repository.save(record)

    result = inspect(manager, record.entry_id, record.task_id)

    assert result.exists is True
    assert result.availability == MemoryIdentityAvailability.EXPIRED
    assert result.lifecycle_status == "expired"


def test_inspect_nonexistent_entry(manager):
    result = inspect(manager, uuid4(), uuid4())

    assert result.exists is False
    assert result.availability == MemoryIdentityAvailability.NOT_FOUND
    assert result.lifecycle_status is None


def test_wrong_task_id_returns_not_found(manager):
    record = create_record()
    manager.remember(
        record,
        requesting_agent="PlanningAgent",
    )

    result = inspect(manager, record.entry_id, uuid4())

    assert result.exists is False
    assert result.availability == MemoryIdentityAvailability.NOT_FOUND


def test_non_coordinator_cannot_inspect_identity(manager):
    record = create_record()

    with pytest.raises(PermissionError):
        manager.inspect_identity(
            record.entry_id,
            record.task_id,
            requesting_agent="PlanningAgent",
        )


def test_unauthorized_requester_cannot_check_existence(manager):
    with pytest.raises(PermissionError):
        manager.inspect_identity(
            uuid4(),
            uuid4(),
            requesting_agent="UnknownAgent",
        )


def test_invalid_entry_id_is_rejected(manager):
    with pytest.raises(TypeError):
        manager.inspect_identity(
            "invalid",
            uuid4(),
            requesting_agent="CoordinatorAgent",
        )


def test_invalid_task_id_is_rejected(manager):
    with pytest.raises(TypeError):
        manager.inspect_identity(
            uuid4(),
            "invalid",
            requesting_agent="CoordinatorAgent",
        )
