
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.prospective_manager import ProspectiveMemoryManager
from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)
from app.memory.repositories.prospective_memory import (
    ProspectiveMemoryRepository,
)
from app.memory.schemas import MemorySensitivity


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "prospective_manager.db")
    database.initialize()

    repository = ProspectiveMemoryRepository(database)
    memory_manager = ProspectiveMemoryManager(repository)
    memory_manager.initialize()

    return memory_manager


def create_record(**overrides):
    now = datetime.now(timezone.utc)

    data = {
        "title": "Review project",
        "description": "Review project changes.",
        "action": "Review and report issues.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "source": ProspectiveMemorySource.USER,
        "source_agent": "CoordinatorAgent",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)

    due_at = data.get("due_at")
    if due_at is not None and due_at < data["created_at"]:
        data["created_at"] = due_at - timedelta(days=1)

    return ProspectiveMemoryRecord(**data)


def test_remember_pending_intention(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.repository.get(record.memory_id) == record


def test_remember_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.remember(
            create_record(),
            requesting_agent="PlanningAgent",
        )


def test_remember_rejects_invalid_record(manager):
    with pytest.raises(TypeError):
        manager.remember(
            "invalid",
            requesting_agent="CoordinatorAgent",
        )


def test_remember_rejects_restricted_sensitivity(manager):
    record = create_record(
        sensitivity=MemorySensitivity.RESTRICTED,
    )

    with pytest.raises(ValueError):
        manager.remember(
            record,
            requesting_agent="CoordinatorAgent",
        )


def test_remember_rejects_untrusted_source_agent(manager):
    record = create_record(source_agent="UnknownAgent")

    with pytest.raises(ValueError):
        manager.remember(
            record,
            requesting_agent="CoordinatorAgent",
        )


def test_get_returns_pending_intention(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        record.memory_id,
        requesting_agent="PlanningAgent",
    )

    assert result is not None
    assert result.memory_id == record.memory_id


def test_get_hides_completed_intention(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now,
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    manager.complete(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.get(
        record.memory_id,
        requesting_agent="PlanningAgent",
    ) is None


def test_get_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.get(
            uuid4(),
            requesting_agent="UnknownAgent",
        )


def test_get_rejects_invalid_memory_id(manager):
    with pytest.raises(TypeError):
        manager.get(
            "invalid",
            requesting_agent="PlanningAgent",
        )


def test_search_returns_active_intentions_only(manager):
    pending = create_record()
    completed = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=datetime.now(timezone.utc),
    )

    manager.remember(pending, requesting_agent="CoordinatorAgent")
    manager.remember(completed, requesting_agent="CoordinatorAgent")

    manager.trigger(
        completed.memory_id,
        requesting_agent="CoordinatorAgent",
    )
    manager.complete(
        completed.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    results = manager.search(
        requesting_agent="PlanningAgent",
    )

    assert len(results) == 1
    assert results[0].memory_id == pending.memory_id


def test_search_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.search(requesting_agent="UnknownAgent")


def test_get_due_returns_due_intentions(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    results = manager.get_due(
        requesting_agent="CoordinatorAgent",
        now=now,
    )

    assert len(results) == 1
    assert results[0].memory_id == record.memory_id


def test_get_due_does_not_change_status(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.get_due(
        requesting_agent="CoordinatorAgent",
        now=now,
    )

    stored = manager.repository.get(record.memory_id)

    assert stored.status == ProspectiveMemoryStatus.PENDING
    assert stored.triggered_at is None


def test_get_due_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.get_due(requesting_agent="UnknownAgent")


def test_trigger_due_time_intention(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    updated = manager.repository.get(record.memory_id)

    assert updated.status == ProspectiveMemoryStatus.TRIGGERED
    assert updated.triggered_at is not None


def test_trigger_rejects_future_time_intention(manager):
    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_trigger_rejects_expired_intention(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        expires_at=now - timedelta(minutes=1),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_trigger_rejects_missing_record(manager):
    assert manager.trigger(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is False


def test_trigger_is_coordinator_only(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    with pytest.raises(PermissionError):
        manager.trigger(
            record.memory_id,
            requesting_agent="PlanningAgent",
        )


def test_complete_triggered_intention(manager):
    record = create_record(
        trigger_type=ProspectiveTriggerType.MANUAL,
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.complete(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    completed = manager.repository.get(record.memory_id)

    assert completed.status == ProspectiveMemoryStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.triggered_at is not None


def test_complete_rejects_pending_intention(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.complete(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_complete_rejects_non_coordinator(manager):
    with pytest.raises(PermissionError):
        manager.complete(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_cancel_pending_intention(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.cancel(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    cancelled = manager.repository.get(record.memory_id)

    assert cancelled.status == ProspectiveMemoryStatus.CANCELLED
    assert cancelled.triggered_at is None


def test_cancel_rejects_triggered_intention(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.cancel(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_cancel_is_coordinator_only(manager):
    with pytest.raises(PermissionError):
        manager.cancel(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_expire_pending_intention(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
    )

    manager.remember(record, requesting_agent="CoordinatorAgent")

    expired = manager.expire(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert expired is True

    updated = manager.get(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )
    assert updated is None


def test_expire_rejects_intention_not_yet_expired(manager):
    record = create_record(
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.expire(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_expire_rejects_intention_without_expiration(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.expire(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_expire_is_coordinator_only(manager):
    with pytest.raises(PermissionError):
        manager.expire(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_completed_intention_cannot_be_triggered_again(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )
    manager.complete(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False


def test_cancelled_intention_cannot_be_triggered(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )
    manager.cancel(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False

def test_protected_intention_cannot_be_triggered(manager):
    record = create_record(is_protected=True)

    manager.remember(record, requesting_agent="CoordinatorAgent")

    assert manager.trigger(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False

    stored = manager.repository.get(record.memory_id)
    assert stored.status == ProspectiveMemoryStatus.PENDING
    assert stored.triggered_at is None


def test_protected_intention_cannot_be_completed(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        status=ProspectiveMemoryStatus.TRIGGERED,
        triggered_at=now,
        is_protected=True,
    )

    # Seed an already-triggered protected record to test completion.
    manager.repository.save(record)

    assert manager.complete(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False

    stored = manager.repository.get(record.memory_id)
    assert stored.status == ProspectiveMemoryStatus.TRIGGERED
    assert stored.completed_at is None


def test_protected_intention_cannot_be_cancelled(manager):
    record = create_record(is_protected=True)

    manager.remember(record, requesting_agent="CoordinatorAgent")

    assert manager.cancel(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False

    stored = manager.repository.get(record.memory_id)
    assert stored.status == ProspectiveMemoryStatus.PENDING


def test_protected_intention_cannot_be_expired(manager):
    now = datetime.now(timezone.utc)

    record = create_record(
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
        expires_at=now - timedelta(minutes=1),
        is_protected=True,
    )

    manager.remember(record, requesting_agent="CoordinatorAgent")

    assert manager.expire(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is False

    stored = manager.repository.get(record.memory_id)
    assert stored.status == ProspectiveMemoryStatus.PENDING
