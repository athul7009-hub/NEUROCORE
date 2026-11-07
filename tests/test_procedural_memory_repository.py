
import pytest
from uuid import uuid4

from app.memory.database import SQLiteDatabase
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
    ProceduralMemoryStatus,
    ProceduralMemoryStep,
)
from app.memory.repositories.procedural_memory import (
    ProceduralMemoryRepository,
)
from app.memory.schemas import MemorySensitivity


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "procedural.db")
    database.initialize()

    repo = ProceduralMemoryRepository(database)
    repo.initialize()

    return repo


def create_record(**overrides):
    data = {
        "name": "Python Project Setup",
        "description": "Steps to initialize a Python project.",
        "when_to_use": "When starting a new Python project.",
        "steps": [
            ProceduralMemoryStep(
                step_number=1,
                instruction="Create a project directory.",
                expected_outcome="Project directory exists.",
            ),
            ProceduralMemoryStep(
                step_number=2,
                instruction="Create a virtual environment.",
                expected_outcome="Virtual environment is ready.",
            ),
        ],
        "source": ProceduralMemorySource.DOCUMENT,
    }
    data.update(overrides)

    return ProceduralMemoryRecord(**data)


def test_initialize_creates_procedural_memory_table(repository):
    with repository.database.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "procedural_memory" in tables


def test_initialize_is_idempotent(repository):
    repository.initialize()
    repository.initialize()


def test_save_and_get_procedural_memory(repository):
    record = create_record()

    repository.save(record)

    retrieved = repository.get(record.procedure_id)

    assert retrieved == record


def test_get_returns_none_for_missing_procedure(repository):
    assert repository.get(uuid4()) is None


def test_duplicate_procedure_id_is_rejected(repository):
    record = create_record()

    repository.save(record)

    with pytest.raises(Exception):
        repository.save(record)


def test_steps_are_persisted_in_order(repository):
    record = create_record()

    repository.save(record)

    retrieved = repository.get(record.procedure_id)

    assert retrieved is not None
    assert [step.step_number for step in retrieved.steps] == [1, 2]
    assert retrieved.steps[0].instruction == (
        "Create a project directory."
    )
    assert retrieved.steps[1].instruction == (
        "Create a virtual environment."
    )


def test_search_by_name(repository):
    python = create_record()
    database = create_record(name="SQLite Backup")

    repository.save(python)
    repository.save(database)

    results = repository.search(name="Python Project Setup")

    assert len(results) == 1
    assert results[0].procedure_id == python.procedure_id


def test_search_by_status(repository):
    candidate = create_record()

    validated = create_record(
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    repository.save(candidate)
    repository.save(validated)

    results = repository.search(
        status=ProceduralMemoryStatus.VALIDATED
    )

    assert len(results) == 1
    assert results[0].procedure_id == validated.procedure_id


def test_search_by_sensitivity(repository):
    internal = create_record()

    public = create_record(
        name="Public Setup Guide",
        sensitivity=MemorySensitivity.PUBLIC,
    )

    repository.save(internal)
    repository.save(public)

    results = repository.search(
        sensitivity=MemorySensitivity.PUBLIC
    )

    assert len(results) == 1
    assert results[0].procedure_id == public.procedure_id


def test_search_supports_multiple_filters(repository):
    matching = create_record(
        status=ProceduralMemoryStatus.VALIDATED,
        sensitivity=MemorySensitivity.PUBLIC,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    repository.save(matching)
    repository.save(create_record())

    results = repository.search(
        name="Python Project Setup",
        status=ProceduralMemoryStatus.VALIDATED,
        sensitivity=MemorySensitivity.PUBLIC,
    )

    assert len(results) == 1
    assert results[0].procedure_id == matching.procedure_id


def test_search_supports_limit_and_offset(repository):
    records = [
        create_record(name=f"Procedure {index}")
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


def test_search_rejects_invalid_offset(repository):
    with pytest.raises(ValueError):
        repository.search(offset=-1)


def test_search_rejects_invalid_name_type(repository):
    with pytest.raises(TypeError):
        repository.search(name=123)


def test_search_rejects_empty_name(repository):
    with pytest.raises(ValueError):
        repository.search(name="   ")


def test_search_rejects_invalid_status(repository):
    with pytest.raises(TypeError):
        repository.search(status="validated")


def test_search_rejects_invalid_sensitivity(repository):
    with pytest.raises(TypeError):
        repository.search(sensitivity="public")


def test_update_existing_record(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "description": "Updated Python project setup procedure.",
            "confidence": 0.9,
        }
    )

    assert repository.update(updated) is True

    retrieved = repository.get(record.procedure_id)

    assert retrieved.description == (
        "Updated Python project setup procedure."
    )
    assert retrieved.confidence == 0.9


def test_update_can_change_procedure_steps(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "steps": [
                ProceduralMemoryStep(
                    step_number=1,
                    instruction="Install Python.",
                ),
            ],
        }
    )

    assert repository.update(updated) is True

    retrieved = repository.get(record.procedure_id)

    assert len(retrieved.steps) == 1
    assert retrieved.steps[0].instruction == "Install Python."


def test_update_returns_false_for_missing_record(repository):
    record = create_record()

    assert repository.update(record) is False


def test_record_survives_database_reinitialization(tmp_path):
    database_path = tmp_path / "persistent.db"

    first_database = SQLiteDatabase(database_path)
    first_database.initialize()

    first_repository = ProceduralMemoryRepository(first_database)
    first_repository.initialize()

    record = create_record()
    first_repository.save(record)

    second_database = SQLiteDatabase(database_path)
    second_database.initialize()

    second_repository = ProceduralMemoryRepository(second_database)
    second_repository.initialize()

    assert second_repository.get(record.procedure_id) == record

