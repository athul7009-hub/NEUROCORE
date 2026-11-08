from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.memory.schemas import MemorySensitivity
from app.memory.working_manager import WorkingMemoryManager
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


@pytest.fixture
def repository():
    return MagicMock()


@pytest.fixture
def manager(repository):
    return WorkingMemoryManager(repository)


@pytest.fixture
def record():
    now = datetime.now(timezone.utc)

    return WorkingMemoryRecord(
        task_id=uuid4(),
        key="analysis_result",
        entry_type=WorkingMemoryEntryType.INTERMEDIATE_RESULT,
        content={"result": "success"},
        source_agent="PlanningAgent",
        sensitivity=MemorySensitivity.INTERNAL,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_initialize_initializes_repository(manager, repository):
    manager.initialize()

    repository.initialize.assert_called_once()


def test_remember_saves_valid_entry(manager, repository, record):
    manager.remember(
        record,
        requesting_agent="PlanningAgent",
    )

    repository.save.assert_called_once_with(record)


def test_remember_rejects_untrusted_agent(
    manager,
    repository,
    record,
):
    with pytest.raises(PermissionError):
        manager.remember(
            record,
            requesting_agent="UnknownAgent",
        )

    repository.save.assert_not_called()


def test_remember_rejects_invalid_record(manager, repository):
    with pytest.raises(TypeError):
        manager.remember(
            object(),
            requesting_agent="PlanningAgent",
        )

    repository.save.assert_not_called()


def test_remember_rejects_source_agent_mismatch(
    manager,
    repository,
    record,
):
    with pytest.raises(ValueError):
        manager.remember(
            record,
            requesting_agent="VerificationAgent",
        )

    repository.save.assert_not_called()


def test_get_returns_entry_from_same_task(
    manager,
    repository,
    record,
):
    repository.get.return_value = record

    result = manager.get(
        record.entry_id,
        record.task_id,
        requesting_agent="VerificationAgent",
    )

    assert result == record
    repository.get.assert_called_once_with(
        record.entry_id,
        record.task_id,
    )


def test_get_returns_none_for_missing_entry(manager, repository):
    repository.get.return_value = None

    result = manager.get(
        uuid4(),
        uuid4(),
        requesting_agent="PlanningAgent",
    )

    assert result is None


def test_get_rejects_untrusted_agent(manager, repository, record):
    with pytest.raises(PermissionError):
        manager.get(
            record.entry_id,
            record.task_id,
            requesting_agent="UnknownAgent",
        )

    repository.get.assert_not_called()


def test_get_rejects_invalid_entry_id(manager, repository, record):
    with pytest.raises(TypeError):
        manager.get(
            "invalid",
            record.task_id,
            requesting_agent="PlanningAgent",
        )

    repository.get.assert_not_called()


def test_get_rejects_invalid_task_id(manager, repository, record):
    with pytest.raises(TypeError):
        manager.get(
            record.entry_id,
            "invalid",
            requesting_agent="PlanningAgent",
        )

    repository.get.assert_not_called()


def test_get_rejects_entry_from_different_task(
    manager,
    repository,
    record,
):
    repository.get.return_value = record

    result = manager.get(
        record.entry_id,
        uuid4(),
        requesting_agent="PlanningAgent",
    )

    assert result is None


def test_search_returns_same_task_entries(
    manager,
    repository,
    record,
):
    repository.search.return_value = [record]

    results = manager.search(
        task_id=record.task_id,
        requesting_agent="VerificationAgent",
    )

    assert results == [record]
    repository.search.assert_called_once()


def test_search_rejects_untrusted_agent(manager, repository, record):
    with pytest.raises(PermissionError):
        manager.search(
            task_id=record.task_id,
            requesting_agent="UnknownAgent",
        )

    repository.search.assert_not_called()


def test_search_rejects_invalid_task_id(manager, repository):
    with pytest.raises(TypeError):
        manager.search(
            task_id="invalid",
            requesting_agent="PlanningAgent",
        )

    repository.search.assert_not_called()


def test_search_rejects_invalid_limit(manager, repository, record):
    with pytest.raises(ValueError):
        manager.search(
            task_id=record.task_id,
            requesting_agent="PlanningAgent",
            limit=101,
        )

    repository.search.assert_not_called()


def test_search_rejects_negative_offset(
    manager,
    repository,
    record,
):
    with pytest.raises(ValueError):
        manager.search(
            task_id=record.task_id,
            requesting_agent="PlanningAgent",
            offset=-1,
        )

    repository.search.assert_not_called()


def test_search_excludes_entries_from_another_task(
    manager,
    repository,
    record,
):
    repository.search.return_value = [
        record.model_copy(update={"task_id": uuid4()})
    ]

    results = manager.search(
        task_id=record.task_id,
        requesting_agent="PlanningAgent",
    )

    assert results == []

def test_update_saves_valid_owner_entry(
    manager,
    repository,
    record,
):
    repository.get.return_value = record
    repository.update.return_value = True

    result = manager.update(
        record,
        requesting_agent="PlanningAgent",
    )

    assert result is True
    repository.get.assert_called_once_with(
        record.entry_id,
        record.task_id,
    )
    repository.update.assert_called_once_with(record)

def test_update_rejects_source_agent_mismatch(
    manager,
    repository,
    record,
):
    with pytest.raises(ValueError):
        manager.update(
            record,
            requesting_agent="VerificationAgent",
        )

    repository.update.assert_not_called()


def test_update_rejects_untrusted_agent(
    manager,
    repository,
    record,
):
    with pytest.raises(PermissionError):
        manager.update(
            record,
            requesting_agent="UnknownAgent",
        )

    repository.update.assert_not_called()


def test_update_rejects_invalid_record(manager, repository):
    with pytest.raises(TypeError):
        manager.update(
            object(),
            requesting_agent="PlanningAgent",
        )

    repository.update.assert_not_called()


def test_cleanup_expired_allows_coordinator(
    manager,
    repository,
):
    repository.delete_expired.return_value = 3

    result = manager.cleanup_expired(
        requesting_agent="CoordinatorAgent",
    )

    assert result == 3
    repository.delete_expired.assert_called_once()


def test_cleanup_expired_rejects_non_coordinator(
    manager,
    repository,
):
    with pytest.raises(PermissionError):
        manager.cleanup_expired(
            requesting_agent="PlanningAgent",
        )

    repository.delete_expired.assert_not_called()