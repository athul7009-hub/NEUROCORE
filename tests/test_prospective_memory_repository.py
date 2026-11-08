
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
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
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "prospective.db")
    database.initialize()

    repo = ProspectiveMemoryRepository(database)
    repo.initialize()

    return repo


def create_record(**overrides):
    now = datetime.now(timezone.utc)

    data = {
        "title": "Review project",
        "description": "Review the latest project changes.",
        "action": "Review changes and report any issues.",
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


def test_initialize_creates_prospective_memory_table(repository):
    with repository.database.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "prospective_memory" in tables


def test_initialize_is_idempotent(repository):
    repository.initialize()
    repository.initialize()


def test_save_and_get_prospective_memory(repository):
    record = create_record()

    repository.save(record)

    assert repository.get(record.memory_id) == record


def test_get_returns_none_for_missing_memory(repository):
    assert repository.get(uuid4()) is None


def test_duplicate_memory_id_is_rejected(repository):
    record = create_record()
    repository.save(record)

    with pytest.raises(Exception):
        repository.save(record)


def test_optional_fields_are_persisted(repository):
    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=datetime.now(timezone.utc) + timedelta(hours=2),
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        priority=ProspectiveMemoryPriority.HIGH,
        source_task_id=uuid4(),
        sensitivity=MemorySensitivity.PUBLIC,
        is_protected=True,
    )

    repository.save(record)

    assert repository.get(record.memory_id) == record


def test_search_by_title(repository):
    matching = create_record()
    other = create_record(title="Prepare documentation")

    repository.save(matching)
    repository.save(other)

    results = repository.search(title="Review project")

    assert len(results) == 1
    assert results[0].memory_id == matching.memory_id


def test_search_by_status(repository):
    pending = create_record()
    cancelled = create_record(
        status=ProspectiveMemoryStatus.CANCELLED,
    )

    repository.save(pending)
    repository.save(cancelled)

    results = repository.search(
        status=ProspectiveMemoryStatus.CANCELLED
    )

    assert len(results) == 1
    assert results[0].memory_id == cancelled.memory_id


def test_search_by_trigger_type(repository):
    manual = create_record()
    event = create_record(
        trigger_type=ProspectiveTriggerType.EVENT,
        trigger_condition="Project approval received",
    )

    repository.save(manual)
    repository.save(event)

    results = repository.search(
        trigger_type=ProspectiveTriggerType.EVENT
    )

    assert len(results) == 1
    assert results[0].memory_id == event.memory_id


def test_search_by_priority(repository):
    normal = create_record()
    critical = create_record(
        priority=ProspectiveMemoryPriority.CRITICAL,
    )

    repository.save(normal)
    repository.save(critical)

    results = repository.search(
        priority=ProspectiveMemoryPriority.CRITICAL
    )

    assert len(results) == 1
    assert results[0].memory_id == critical.memory_id


def test_search_by_sensitivity(repository):
    internal = create_record()
    public = create_record(
        sensitivity=MemorySensitivity.PUBLIC,
    )

    repository.save(internal)
    repository.save(public)

    results = repository.search(
        sensitivity=MemorySensitivity.PUBLIC
    )

    assert len(results) == 1
    assert results[0].memory_id == public.memory_id


def test_search_by_source(repository):
    user_record = create_record()
    agent_record = create_record(
        source=ProspectiveMemorySource.AGENT,
        source_agent="PlanningAgent",
    )

    repository.save(user_record)
    repository.save(agent_record)

    results = repository.search(
        source=ProspectiveMemorySource.AGENT
    )

    assert len(results) == 1
    assert results[0].memory_id == agent_record.memory_id


def test_search_by_source_agent(repository):
    coordinator = create_record()
    planner = create_record(
        source_agent="PlanningAgent",
        source=ProspectiveMemorySource.AGENT,
    )

    repository.save(coordinator)
    repository.save(planner)

    results = repository.search(source_agent="PlanningAgent")

    assert len(results) == 1
    assert results[0].memory_id == planner.memory_id


def test_search_supports_multiple_filters(repository):
    matching = create_record(
        status=ProspectiveMemoryStatus.PENDING,
        trigger_type=ProspectiveTriggerType.TIME,
        priority=ProspectiveMemoryPriority.HIGH,
        sensitivity=MemorySensitivity.PUBLIC,
        due_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    repository.save(matching)
    repository.save(create_record())

    results = repository.search(
        status=ProspectiveMemoryStatus.PENDING,
        trigger_type=ProspectiveTriggerType.TIME,
        priority=ProspectiveMemoryPriority.HIGH,
        sensitivity=MemorySensitivity.PUBLIC,
    )

    assert len(results) == 1
    assert results[0].memory_id == matching.memory_id


def test_search_supports_limit_and_offset(repository):
    records = [
        create_record(title=f"Intention {index}")
        for index in range(4)
    ]

    for record in records:
        repository.save(record)

    results = repository.search(limit=2, offset=1)

    assert len(results) == 2


def test_search_rejects_invalid_limit(repository):
    with pytest.raises(ValueError):
        repository.search(limit=0)

    with pytest.raises(ValueError):
        repository.search(limit=101)


def test_search_rejects_boolean_limit(repository):
    with pytest.raises(TypeError):
        repository.search(limit=True)


def test_search_rejects_invalid_offset(repository):
    with pytest.raises(ValueError):
        repository.search(offset=-1)


def test_search_rejects_boolean_offset(repository):
    with pytest.raises(TypeError):
        repository.search(offset=True)


def test_search_rejects_invalid_title_type(repository):
    with pytest.raises(TypeError):
        repository.search(title=123)


def test_search_rejects_empty_title(repository):
    with pytest.raises(ValueError):
        repository.search(title="   ")


def test_search_rejects_invalid_status(repository):
    with pytest.raises(TypeError):
        repository.search(status="pending")


def test_search_rejects_invalid_trigger_type(repository):
    with pytest.raises(TypeError):
        repository.search(trigger_type="time")


def test_search_rejects_invalid_priority(repository):
    with pytest.raises(TypeError):
        repository.search(priority="high")


def test_search_rejects_invalid_sensitivity(repository):
    with pytest.raises(TypeError):
        repository.search(sensitivity="public")


def test_search_rejects_invalid_source(repository):
    with pytest.raises(TypeError):
        repository.search(source="user")


def test_search_rejects_invalid_source_agent(repository):
    with pytest.raises(TypeError):
        repository.search(source_agent=123)


def test_search_rejects_empty_source_agent(repository):
    with pytest.raises(ValueError):
        repository.search(source_agent="   ")


def test_update_existing_record(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "description": "Updated project review description.",
            "priority": ProspectiveMemoryPriority.HIGH,
        }
    )

    assert repository.update(
        updated,
        expected_status=record.status,
    ) is True

    retrieved = repository.get(record.memory_id)

    assert retrieved.description == (
        "Updated project review description."
    )
    assert retrieved.priority == ProspectiveMemoryPriority.HIGH


def test_update_can_change_lifecycle_status(repository):
    record = create_record()
    repository.save(record)

    triggered_at = datetime.now(timezone.utc)
    completed_at = triggered_at + timedelta(seconds=1)

    updated = record.model_copy(
        update={
            "status": ProspectiveMemoryStatus.COMPLETED,
            "triggered_at": triggered_at,
            "completed_at": completed_at,
        }
    )

    assert repository.update(
        updated,
        expected_status=record.status,
    ) is True

    retrieved = repository.get(record.memory_id)

    assert retrieved.status == ProspectiveMemoryStatus.COMPLETED
    assert retrieved.completed_at == updated.completed_at


def test_update_returns_false_for_missing_record(repository):
    record = create_record()

    assert repository.update(
        record,
        expected_status=record.status,
    ) is False


def test_update_cannot_enable_protection(repository):
    record = create_record(is_protected=False)
    repository.save(record)

    updated = record.model_copy(
        update={"is_protected": True}
    )

    assert repository.update(
        updated,
        expected_status=record.status,
    ) is True

    stored = repository.get(record.memory_id)

    assert stored is not None
    assert stored.is_protected is False


def test_update_cannot_disable_protection(repository):
    record = create_record(is_protected=True)
    repository.save(record)

    updated = record.model_copy(
        update={"is_protected": False}
    )

    assert repository.update(
        updated,
        expected_status=record.status,
    ) is False

    stored = repository.get(record.memory_id)

    assert stored is not None
    assert stored.is_protected is True


def test_update_rejects_stale_expected_status(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "status": ProspectiveMemoryStatus.CANCELLED,
        }
    )

    assert repository.update(
        updated,
        expected_status=ProspectiveMemoryStatus.TRIGGERED,
    ) is False

    stored = repository.get(record.memory_id)

    assert stored is not None
    assert stored.status == ProspectiveMemoryStatus.PENDING


def test_get_due_returns_pending_time_intentions(repository):
    now = datetime.now(timezone.utc)

    due = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    future = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now + timedelta(hours=1),
    )

    manual = create_record()

    repository.save(due)
    repository.save(future)
    repository.save(manual)

    results = repository.get_due(now=now)

    assert [record.memory_id for record in results] == [due.memory_id]


def test_get_due_excludes_non_pending_intentions(repository):
    now = datetime.now(timezone.utc)
    triggered_at = now - timedelta(minutes=1)

    completed = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        status=ProspectiveMemoryStatus.COMPLETED,
        triggered_at=triggered_at,
        completed_at=now,
    )

    cancelled = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        status=ProspectiveMemoryStatus.CANCELLED,
    )

    expired = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        status=ProspectiveMemoryStatus.EXPIRED,
        expires_at=now - timedelta(minutes=1),
    )

    for record in (completed, cancelled, expired):
        repository.save(record)

    assert repository.get_due(now=now) == []


def test_get_due_excludes_expired_intentions(repository):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        expires_at=now,
    )

    repository.save(record)

    assert repository.get_due(now=now) == []


def test_get_due_includes_intentions_without_expiration(repository):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    repository.save(record)

    results = repository.get_due(now=now)

    assert len(results) == 1
    assert results[0].memory_id == record.memory_id


def test_get_due_orders_by_priority(repository):
    now = datetime.now(timezone.utc)

    low = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
        priority=ProspectiveMemoryPriority.LOW,
    )

    critical = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=10),
        priority=ProspectiveMemoryPriority.CRITICAL,
    )

    normal = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=15),
        priority=ProspectiveMemoryPriority.NORMAL,
    )

    for record in (low, normal, critical):
        repository.save(record)

    results = repository.get_due(now=now)

    assert [record.memory_id for record in results] == [
        critical.memory_id,
        normal.memory_id,
        low.memory_id,
    ]


def test_get_due_supports_limit(repository):
    now = datetime.now(timezone.utc)

    for index in range(3):
        repository.save(
            create_record(
                trigger_type=ProspectiveTriggerType.TIME,
                due_at=now - timedelta(minutes=index + 1),
            )
        )

    assert len(repository.get_due(now=now, limit=2)) == 2


def test_get_due_rejects_invalid_limit(repository):
    with pytest.raises(ValueError):
        repository.get_due(limit=0)

    with pytest.raises(ValueError):
        repository.get_due(limit=101)


def test_get_due_rejects_boolean_limit(repository):
    with pytest.raises(TypeError):
        repository.get_due(limit=True)


def test_get_due_rejects_naive_datetime(repository):
    with pytest.raises(ValueError):
        repository.get_due(now=datetime(2026, 1, 1))


def test_get_due_does_not_change_intention_status(repository):
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=5),
    )

    repository.save(record)
    repository.get_due(now=now)

    retrieved = repository.get(record.memory_id)

    assert retrieved.status == ProspectiveMemoryStatus.PENDING


def test_record_survives_database_reinitialization(tmp_path):
    database_path = tmp_path / "persistent.db"

    first_database = SQLiteDatabase(database_path)
    first_database.initialize()

    first_repository = ProspectiveMemoryRepository(first_database)
    first_repository.initialize()

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    first_repository.save(record)

    second_database = SQLiteDatabase(database_path)
    second_database.initialize()

    second_repository = ProspectiveMemoryRepository(second_database)
    second_repository.initialize()

    assert second_repository.get(record.memory_id) == record
