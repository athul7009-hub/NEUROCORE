
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
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
    MemoryLifecycleStatus,
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

    assert manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    ) == record


def test_missing_task_returns_none(manager):
    assert manager.get_task(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is None


def test_get_recent_tasks(manager):
    first = create_record()
    second = create_record()

    manager.remember_task(first)
    manager.remember_task(second)

    recent = manager.get_recent_tasks(
        limit=2,
        requesting_agent="CoordinatorAgent",
    )

    assert len(recent) == 2
    assert recent[0].task_id == second.task_id


def test_invalid_record_is_rejected(manager):
    with pytest.raises(TypeError):
        manager.remember_task({"summary": "Invalid memory"})


def test_initialize_is_safe_to_repeat(manager):
    manager.initialize()
    manager.initialize()


def test_rejected_memory_is_not_saved(manager):
    record = create_record()

    with pytest.raises(ValueError, match="rejected by storage policy"):
        manager.remember_task(
            record,
            sensitivity=MemorySensitivity.CONFIDENTIAL,
        )

    assert manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    ) is None


def test_approved_memory_is_saved(manager):
    record = create_record()

    manager.remember_task(
        record,
        sensitivity=MemorySensitivity.PUBLIC,
    )

    stored_record = manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored_record is not None
    assert stored_record.sensitivity == MemorySensitivity.PUBLIC
    assert stored_record.source == MemorySource.COORDINATOR

    # The original record must remain unchanged.
    assert record.sensitivity == MemorySensitivity.INTERNAL


def test_get_recent_tasks_with_filters(manager):
    matching = create_record()

    different_intent = create_record().model_copy(
        update={"intent": "code_review"}
    )

    different_agent = create_record().model_copy(
        update={"agent_name": "CodeReviewAgent"}
    )

    for record in (matching, different_intent, different_agent):
        manager.remember_task(record)

    results = manager.get_recent_tasks(
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        requesting_agent="CoordinatorAgent",
    )

    assert len(results) == 1
    assert results[0].task_id == matching.task_id


# --------------------------------------------------
# Retrieval authorization tests
# --------------------------------------------------


def test_unknown_agent_cannot_retrieve_memory(manager):
    record = create_record()
    manager.remember_task(record)

    with pytest.raises(PermissionError, match="Unauthorized"):
        manager.get_task(
            record.task_id,
            requesting_agent="UnknownAgent",
        )


@pytest.mark.parametrize(
    "requesting_agent",
    [None, "", "   ", 123],
)
def test_invalid_requester_is_rejected(manager, requesting_agent):
    with pytest.raises(PermissionError, match="Unauthorized"):
        manager.get_recent_tasks(
            requesting_agent=requesting_agent,
        )


def test_trusted_agent_cannot_retrieve_confidential_memory(manager):
    record = create_record().model_copy(
        update={
            "sensitivity": MemorySensitivity.CONFIDENTIAL,
        }
    )

    # Simulate an existing confidential database record.
    manager.repository.save(record)

    result = manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result is None


def test_recent_tasks_exclude_unauthorized_memories(manager):
    public_record = create_record().model_copy(
        update={
            "sensitivity": MemorySensitivity.PUBLIC,
        }
    )

    confidential_record = create_record().model_copy(
        update={
            "sensitivity": MemorySensitivity.CONFIDENTIAL,
        }
    )

    manager.repository.save(public_record)
    manager.repository.save(confidential_record)

    results = manager.get_recent_tasks(
        limit=10,
        requesting_agent="CoordinatorAgent",
    )

    retrieved_ids = {record.task_id for record in results}

    assert public_record.task_id in retrieved_ids
    assert confidential_record.task_id not in retrieved_ids


def test_recent_tasks_retrieve_authorized_records_beyond_first_batch(manager):
    now = datetime.now(timezone.utc)

    confidential_records = [
        create_record().model_copy(
            update={
                "sensitivity": MemorySensitivity.CONFIDENTIAL,
                "completed_at": now,
            }
        )
        for _ in range(100)
    ]

    public_record = create_record().model_copy(
        update={
            "sensitivity": MemorySensitivity.PUBLIC,
            "completed_at": now.replace(year=now.year - 1),
        }
    )

    for record in confidential_records:
        manager.repository.save(record)

    manager.repository.save(public_record)

    results = manager.get_recent_tasks(
        limit=1,
        requesting_agent="CoordinatorAgent",
    )

    assert len(results) == 1
    assert results[0].task_id == public_record.task_id
@pytest.mark.parametrize(
    "limit",
    [0, 101, True, 1.5, "5"],
)
def test_get_recent_tasks_rejects_invalid_limits(manager, limit):
    with pytest.raises((TypeError, ValueError)):
        manager.get_recent_tasks(
            limit=limit,
            requesting_agent="CoordinatorAgent",
        )


def test_legacy_source_is_rejected(manager):
    with pytest.raises(ValueError, match="rejected by storage policy"):
        manager.remember_task(
            create_record(),
            source=MemorySource.LEGACY,
        )


def test_system_source_is_accepted(manager):
    record = create_record()

    manager.remember_task(
        record,
        source=MemorySource.SYSTEM,
    )

    stored_record = manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored_record is not None
    assert stored_record.source == MemorySource.SYSTEM
def test_record_usage_requires_trusted_agent(manager):
    record = create_record()
    manager.remember_task(record)

    with pytest.raises(PermissionError, match="Unauthorized"):
        manager.record_usage(
            [record.task_id],
            requesting_agent="UnknownAgent",
        )
from datetime import timedelta
from types import SimpleNamespace


def create_archivable_record():
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=120)

    return create_record().model_copy(
        update={
            "created_at": old,
            "completed_at": old,
            "last_used_at": old,
            "usage_tracked": True,
            "use_count": 0,
        }
    )


def test_assess_retention_returns_eligibility(manager):
    record = create_archivable_record()
    manager.remember_task(record)

    results = manager.assess_retention(
        requesting_agent="CoordinatorAgent",
    )

    assert len(results) == 1
    assessed_record, assessment = results[0]

    assert assessed_record.task_id == record.task_id
    assert assessment.eligible is True


def test_archive_is_disabled_by_default(manager, monkeypatch):
    record = create_archivable_record()
    manager.remember_task(record)

    monkeypatch.setattr(
        "app.memory.manager.settings",
        SimpleNamespace(memory_automatic_archival_enabled=False),
    )

    with pytest.raises(PermissionError, match="disabled"):
        manager.archive_task(
            record.task_id,
            requesting_agent="CoordinatorAgent",
        )

    assert manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    ) is not None


def test_archive_requires_coordinator(manager):
    record = create_archivable_record()
    manager.remember_task(record)

    with pytest.raises(PermissionError, match="Only the coordinator"):
        manager.archive_task(
            record.task_id,
            requesting_agent="PlanningAgent",
        )


def test_restore_requires_coordinator(manager):
    record = create_archivable_record()
    manager.remember_task(record)
    manager.repository.archive(record.task_id)

    with pytest.raises(PermissionError, match="Only the coordinator"):
        manager.restore_task(
            record.task_id,
            requesting_agent="PlanningAgent",
        )


def test_archived_memories_are_retrievable_as_history(manager):
    record = create_archivable_record()
    manager.remember_task(record)
    manager.repository.archive(record.task_id)

    # Archived memories must not appear in normal retrieval.
    assert manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    ) is None

    # Authorized historical retrieval should still work.
    archived = manager.get_archived_tasks(
        requesting_agent="CoordinatorAgent",
    )

    assert len(archived) == 1
    assert archived[0].task_id == record.task_id


def test_archived_retrieval_rejects_untrusted_agent(manager):
    record = create_archivable_record()
    manager.remember_task(record)
    manager.repository.archive(record.task_id)

    with pytest.raises(PermissionError, match="Unauthorized"):
        manager.get_archived_tasks(
            requesting_agent="UnknownAgent",
        )


def test_restore_returns_memory_to_active_retrieval(manager):
    record = create_archivable_record()
    manager.remember_task(record)
    manager.repository.archive(record.task_id)

    restored = manager.restore_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert restored is True

    retrieved = manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert retrieved is not None
    assert retrieved.lifecycle_status == MemoryLifecycleStatus.ACTIVE
    assert retrieved.archived_at is None


def test_archive_ineligible_memory_is_rejected(manager, monkeypatch):
    record = create_record()
    manager.remember_task(record)

    monkeypatch.setattr(
        "app.memory.manager.settings",
        SimpleNamespace(memory_automatic_archival_enabled=True),
    )

    with pytest.raises(ValueError, match="not eligible"):
        manager.archive_task(
            record.task_id,
            requesting_agent="CoordinatorAgent",
        )
def test_non_coordinator_cannot_assess_retention(manager):
    with pytest.raises(PermissionError, match="Only the coordinator"):
        manager.assess_retention(
            requesting_agent="PlanningAgent",
        )


def test_archived_retrieval_does_not_authorize_active_memory(manager):
    record = create_record()
    manager.remember_task(record)

    assert manager.policy.evaluate_archived_retrieval(
        record,
        "CoordinatorAgent",
    ) is False