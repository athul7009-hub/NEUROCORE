import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.schemas import MemorySensitivity
from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "semantic_manager.db")
    database.initialize()

    repository = SemanticMemoryRepository(database)
    memory_manager = SemanticMemoryManager(repository)
    memory_manager.initialize()

    return memory_manager


def create_record(**overrides):
    data = {
        "subject": "Python",
        "predicate": "is_a",
        "object": "Programming Language",
        "source": SemanticMemorySource.DOCUMENT,
    }
    data.update(overrides)

    return SemanticMemoryRecord(**data)


def test_remember_candidate(manager):
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


def test_remember_rejects_non_candidate_record(manager):
    record = create_record(
        status=SemanticMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    with pytest.raises(ValueError):
        manager.remember(
            record,
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


def test_get_hides_candidate_memories(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        record.memory_id,
        requesting_agent="PlanningAgent",
    )

    assert result is None


def test_get_returns_validated_memory(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        record.memory_id,
        requesting_agent="PlanningAgent",
    )

    assert result is not None
    assert result.status == SemanticMemoryStatus.VALIDATED


def test_get_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.get(
            create_record().memory_id,
            requesting_agent="UnknownAgent",
        )


def test_get_rejects_invalid_memory_id(manager):
    with pytest.raises(TypeError):
        manager.get(
            "invalid",
            requesting_agent="PlanningAgent",
        )


def test_search_returns_validated_memories_only(manager):
    candidate = create_record()
    validated = create_record(subject="SQLite")

    manager.remember(candidate, requesting_agent="CoordinatorAgent")
    manager.remember(validated, requesting_agent="CoordinatorAgent")

    manager.validate(
        validated.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    results = manager.search(
        requesting_agent="PlanningAgent",
    )

    assert len(results) == 1
    assert results[0].memory_id == validated.memory_id


def test_get_candidates_is_coordinator_only(manager):
    with pytest.raises(PermissionError):
        manager.get_candidates(
            requesting_agent="PlanningAgent",
        )


def test_get_candidates_returns_candidate_records(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    results = manager.get_candidates(
        requesting_agent="CoordinatorAgent",
    )

    assert len(results) == 1
    assert results[0].memory_id == record.memory_id


def test_validate_candidate(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.validate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    validated = manager.repository.get(record.memory_id)

    assert validated.status == SemanticMemoryStatus.VALIDATED
    assert validated.validated_by == "CoordinatorAgent"
    assert validated.validated_at is not None


def test_validate_rejects_non_coordinator(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    with pytest.raises(PermissionError):
        manager.validate(
            record.memory_id,
            requesting_agent="PlanningAgent",
        )


def test_validate_returns_false_for_missing_record(manager):
    from uuid import uuid4

    assert manager.validate(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is False


def test_deprecate_validated_memory(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.deprecate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    deprecated = manager.repository.get(record.memory_id)

    assert deprecated.status == SemanticMemoryStatus.DEPRECATED
    assert deprecated.validated_at is None
    assert deprecated.validated_by is None


def test_deprecate_returns_false_for_missing_record(manager):
    from uuid import uuid4

    assert manager.deprecate(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is False


def test_deprecated_memory_cannot_be_retrieved(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    manager.deprecate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.get(
        record.memory_id,
        requesting_agent="PlanningAgent",
    ) is None