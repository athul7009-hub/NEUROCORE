
import pytest

from uuid import uuid4

from app.memory.database import SQLiteDatabase
from app.memory.repositories.procedural_memory import (
    ProceduralMemoryRepository,
)
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
    ProceduralMemoryStatus,
)
from app.memory.schemas import MemorySensitivity


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "procedural_manager.db")
    database.initialize()

    repository = ProceduralMemoryRepository(database)
    memory_manager = ProceduralMemoryManager(repository)
    memory_manager.initialize()

    return memory_manager


def create_record(**overrides):
    data = {
        "name": "Python project setup",
        "description": "Steps to set up a Python project.",
        "when_to_use": "When starting a new Python project.",
        "steps": [
            {
                "step_number": 1,
                "instruction": "Create a project directory.",
                "expected_outcome": "Project directory exists.",
            },
            {
                "step_number": 2,
                "instruction": "Create a virtual environment.",
                "expected_outcome": "Virtual environment is ready.",
            },
        ],
        "source": ProceduralMemorySource.DOCUMENT,
    }
    data.update(overrides)

    return ProceduralMemoryRecord(**data)


def test_remember_candidate(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.repository.get(record.procedure_id) == record


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
        status=ProceduralMemoryStatus.VALIDATED,
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


def test_get_hides_candidate_procedures(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        record.procedure_id,
        requesting_agent="PlanningAgent",
    )

    assert result is None


def test_get_returns_validated_procedure(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    result = manager.get(
        record.procedure_id,
        requesting_agent="PlanningAgent",
    )

    assert result is not None
    assert result.status == ProceduralMemoryStatus.VALIDATED


def test_get_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.get(
            create_record().procedure_id,
            requesting_agent="UnknownAgent",
        )


def test_get_rejects_invalid_procedure_id(manager):
    with pytest.raises(TypeError):
        manager.get(
            "invalid",
            requesting_agent="PlanningAgent",
        )


def test_search_returns_validated_procedures_only(manager):
    candidate = create_record()
    validated = create_record(name="SQLite database setup")

    manager.remember(candidate, requesting_agent="CoordinatorAgent")
    manager.remember(validated, requesting_agent="CoordinatorAgent")

    manager.validate(
        validated.procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    results = manager.search(
        requesting_agent="PlanningAgent",
    )

    assert len(results) == 1
    assert results[0].procedure_id == validated.procedure_id


def test_search_filters_by_name(manager):
    first = create_record(name="Python project setup")
    second = create_record(name="SQLite database setup")

    manager.remember(first, requesting_agent="CoordinatorAgent")
    manager.remember(second, requesting_agent="CoordinatorAgent")

    manager.validate(first.procedure_id, requesting_agent="CoordinatorAgent")
    manager.validate(second.procedure_id, requesting_agent="CoordinatorAgent")

    results = manager.search(
        requesting_agent="PlanningAgent",
        name="Python project setup",
    )

    assert len(results) == 1
    assert results[0].procedure_id == first.procedure_id


def test_search_rejects_unauthorized_agent(manager):
    with pytest.raises(PermissionError):
        manager.search(requesting_agent="UnknownAgent")


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
    assert results[0].procedure_id == record.procedure_id


def test_validate_candidate(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.validate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    validated = manager.repository.get(record.procedure_id)

    assert validated.status == ProceduralMemoryStatus.VALIDATED
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
            record.procedure_id,
            requesting_agent="PlanningAgent",
        )


def test_validate_returns_false_for_missing_record(manager):
    assert manager.validate(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is False


def test_deprecate_validated_procedure(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.deprecate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    ) is True

    deprecated = manager.repository.get(record.procedure_id)

    assert deprecated.status == ProceduralMemoryStatus.DEPRECATED
    assert deprecated.validated_at is None
    assert deprecated.validated_by is None


def test_deprecate_returns_false_for_missing_record(manager):
    assert manager.deprecate(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is False


def test_deprecated_procedure_cannot_be_retrieved(manager):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    manager.validate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    manager.deprecate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert manager.get(
        record.procedure_id,
        requesting_agent="PlanningAgent",
    ) is None
