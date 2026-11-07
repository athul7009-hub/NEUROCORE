
import pytest
from uuid import uuid4

from app.memory.database import SQLiteDatabase
from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.schemas import MemorySensitivity
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "semantic.db")
    database.initialize()

    repo = SemanticMemoryRepository(database)
    repo.initialize()

    return repo


def create_record(**overrides):
    data = {
        "subject": "Python",
        "predicate": "is_a",
        "object": "Programming Language",
        "source": SemanticMemorySource.DOCUMENT,
    }
    data.update(overrides)

    return SemanticMemoryRecord(**data)


def test_initialize_creates_semantic_memory_table(repository):
    with repository.database.connection() as connection:
        tables = {
            row["name"]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "semantic_memory" in tables


def test_initialize_is_idempotent(repository):
    repository.initialize()
    repository.initialize()


def test_save_and_get_semantic_memory(repository):
    record = create_record()

    repository.save(record)

    retrieved = repository.get(record.memory_id)

    assert retrieved == record


def test_get_returns_none_for_missing_memory(repository):
    assert repository.get(uuid4()) is None


def test_duplicate_memory_id_is_rejected(repository):
    record = create_record()

    repository.save(record)

    with pytest.raises(Exception):
        repository.save(record)


def test_search_by_subject(repository):
    python = create_record()
    java = create_record(subject="Java")

    repository.save(python)
    repository.save(java)

    results = repository.search(subject="Python")

    assert len(results) == 1
    assert results[0].memory_id == python.memory_id


def test_search_by_predicate(repository):
    first = create_record(predicate="is_a")
    second = create_record(predicate="uses")

    repository.save(first)
    repository.save(second)

    results = repository.search(predicate="uses")

    assert len(results) == 1
    assert results[0].memory_id == second.memory_id


def test_search_by_status(repository):
    candidate = create_record()

    validated = create_record(
        status=SemanticMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=(
            create_record().created_at
        ),
    )

    repository.save(candidate)
    repository.save(validated)

    results = repository.search(
        status=SemanticMemoryStatus.VALIDATED
    )

    assert len(results) == 1
    assert results[0].memory_id == validated.memory_id


def test_search_by_sensitivity(repository):
    internal = create_record()

    public = create_record(
        subject="SQLite",
        sensitivity=MemorySensitivity.PUBLIC,
    )

    repository.save(internal)
    repository.save(public)

    results = repository.search(
        sensitivity=MemorySensitivity.PUBLIC
    )

    assert len(results) == 1
    assert results[0].memory_id == public.memory_id


def test_search_supports_multiple_filters(repository):
    matching = create_record(
        status=SemanticMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    repository.save(matching)
    repository.save(create_record())

    results = repository.search(
        subject="Python",
        predicate="is_a",
        status=SemanticMemoryStatus.VALIDATED,
    )

    assert len(results) == 1
    assert results[0].memory_id == matching.memory_id


def test_search_supports_limit_and_offset(repository):
    records = [
        create_record(subject=f"Language {index}")
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


def test_search_rejects_invalid_status(repository):
    with pytest.raises(TypeError):
        repository.search(status="validated")


def test_search_rejects_invalid_sensitivity(repository):
    with pytest.raises(TypeError):
        repository.search(sensitivity="public")


def test_search_rejects_empty_subject(repository):
    with pytest.raises(ValueError):
        repository.search(subject="   ")


def test_update_existing_record(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "object": "High-level Programming Language",
        }
    )

    assert repository.update(updated) is True

    retrieved = repository.get(record.memory_id)

    assert retrieved.object == "High-level Programming Language"


def test_update_returns_false_for_missing_record(repository):
    record = create_record()

    assert repository.update(record) is False


def test_record_survives_database_reinitialization(tmp_path):
    database_path = tmp_path / "persistent.db"

    first_database = SQLiteDatabase(database_path)
    first_database.initialize()

    first_repository = SemanticMemoryRepository(first_database)
    first_repository.initialize()

    record = create_record()
    first_repository.save(record)

    second_database = SQLiteDatabase(database_path)
    second_database.initialize()

    second_repository = SemanticMemoryRepository(second_database)
    second_repository.initialize()

    assert second_repository.get(record.memory_id) == record
