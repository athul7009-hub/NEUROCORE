
from datetime import datetime, timezone

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.meta_conflict_manager import MetaMemoryConflictManager
from app.memory.meta_conflict_schemas import (
    MetaMemoryConflictRecord,
    MetaMemoryConflictStatus,
    MetaMemoryConflictType,
)
from app.memory.repositories.meta_conflict import (
    MetaMemoryConflictRepository,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "conflict_manager.db")
    database.initialize()

    repository = MetaMemoryConflictRepository(database)
    manager = MetaMemoryConflictManager(repository)
    manager.initialize()

    return manager


@pytest.fixture
def valid_record():
    return MetaMemoryConflictRecord(
        memory_type_a="semantic",
        memory_id_a="memory-1",
        memory_type_b="procedural",
        memory_id_b="memory-2",
        conflict_type=MetaMemoryConflictType.FACTUAL,
        confidence_score=0.9,
        rationale="The memories contain contradictory information.",
    )


@pytest.fixture
def stored_conflict(manager, valid_record):
    manager.remember(
        valid_record,
        requesting_agent="CoordinatorAgent",
    )
    return valid_record


def test_remember_stores_detected_conflict(manager, valid_record):
    manager.remember(
        valid_record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.get(
        valid_record.conflict_id,
        requesting_agent="CoordinatorAgent",
    ) == valid_record


def test_remember_rejects_non_conflict_record(manager):
    with pytest.raises(TypeError):
        manager.remember(
            object(),
            requesting_agent="CoordinatorAgent",
        )


def test_remember_rejects_non_detected_conflict(manager, valid_record):
    reviewed = datetime.now(timezone.utc)

    confirmed = MetaMemoryConflictRecord.model_validate({
        **valid_record.model_dump(),
        "status": MetaMemoryConflictStatus.CONFIRMED,
        "reviewed_at": reviewed,
    })

    with pytest.raises(ValueError):
        manager.remember(
            confirmed,
            requesting_agent="CoordinatorAgent",
        )


def test_only_coordinator_can_store(manager, valid_record):
    with pytest.raises(PermissionError):
        manager.remember(
            valid_record,
            requesting_agent="PlanningAgent",
        )


def test_untrusted_agent_cannot_retrieve(manager, stored_conflict):
    with pytest.raises(PermissionError):
        manager.get(
            stored_conflict.conflict_id,
            requesting_agent="UnknownAgent",
        )


def test_get_returns_none_for_missing_conflict(manager):
    from uuid import uuid4

    assert manager.get(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is None


def test_search_returns_conflicts(manager, stored_conflict):
    results = manager.search(
        requesting_agent="CoordinatorAgent",
    )

    assert len(results) == 1
    assert results[0].conflict_id == stored_conflict.conflict_id


def test_confirm_detected_conflict(manager, stored_conflict):
    assert manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result.status == MetaMemoryConflictStatus.CONFIRMED
    assert result.reviewed_at is not None


def test_dismiss_detected_conflict(manager, stored_conflict):
    assert manager.dismiss(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result.status == MetaMemoryConflictStatus.DISMISSED


def test_resolve_confirmed_conflict(manager, stored_conflict):
    manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.resolve(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result.status == MetaMemoryConflictStatus.RESOLVED


def test_cannot_resolve_detected_conflict(manager, stored_conflict):
    assert not manager.resolve(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )


def test_cannot_confirm_twice(manager, stored_conflict):
    manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert not manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )


def test_dismissed_conflict_is_terminal(manager, stored_conflict):
    manager.dismiss(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert not manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert not manager.resolve(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )


def test_resolved_conflict_is_terminal(manager, stored_conflict):
    manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )
    manager.resolve(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert not manager.confirm(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )

    assert not manager.dismiss(
        stored_conflict.conflict_id,
        requesting_agent="CoordinatorAgent",
    )


def test_only_coordinator_can_review(manager, stored_conflict):
    with pytest.raises(PermissionError):
        manager.confirm(
            stored_conflict.conflict_id,
            requesting_agent="PlanningAgent",
        )


def test_invalid_conflict_id_is_rejected(manager):
    with pytest.raises(TypeError):
        manager.get(
            "invalid-id",
            requesting_agent="CoordinatorAgent",
        )
