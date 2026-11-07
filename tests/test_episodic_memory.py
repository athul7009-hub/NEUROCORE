
import sqlite3
from uuid import uuid4

import pytest
from datetime import datetime, timezone
from app.memory.database import SQLiteDatabase
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "memory.db")
    database.initialize()

    repo = EpisodicMemoryRepository(database)
    repo.initialize()

    return repo


def create_record():
    now = datetime.now(timezone.utc)

    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Analyzed a project folder.",
        created_at=now,
    )


def test_save_and_retrieve_memory(repository):
    record = create_record()

    repository.save(record)
    retrieved = repository.get(record.task_id)

    assert retrieved == record


def test_missing_memory_returns_none(repository):
    assert repository.get(uuid4()) is None


def test_duplicate_task_id_is_rejected(repository):
    record = create_record()

    repository.save(record)

    with pytest.raises(sqlite3.IntegrityError):
        repository.save(record)


def test_recent_memories(repository):
    first = create_record()
    second = create_record()

    repository.save(first)
    repository.save(second)

    recent = repository.get_recent(limit=2)

    assert len(recent) == 2
    assert recent[0].task_id == second.task_id


def test_legacy_database_migration(tmp_path):
    database = SQLiteDatabase(tmp_path / "legacy.db")
    database.initialize()

    # Create the old table structure without metadata columns.
    with database.connection() as connection:
        connection.execute(
            """
            CREATE TABLE episodic_memory (
                task_id TEXT PRIMARY KEY,
                intent TEXT NOT NULL,
                status TEXT NOT NULL,
                agent_name TEXT NOT NULL,
                summary TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT NOT NULL
            )
            """
        )

        now = datetime.now(timezone.utc).isoformat()

        connection.execute(
            """
            INSERT INTO episodic_memory (
                task_id, intent, status, agent_name,
                summary, created_at, completed_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(uuid4()),
                "file_analysis",
                "completed",
                "FileAnalysisAgent",
                "Legacy memory record.",
                now,
                now,
            ),
        )

    repository = EpisodicMemoryRepository(database)
    repository.initialize()

    with database.connection() as connection:
        row = connection.execute(
            "SELECT * FROM episodic_memory"
        ).fetchone()

    assert row["sensitivity"] == "legacy_unclassified"
    assert row["source"] == "legacy"

    # Reinitialization must preserve migrated values.
    repository.initialize()

    with database.connection() as connection:
        migrated_row = connection.execute(
            "SELECT * FROM episodic_memory"
        ).fetchone()

    assert migrated_row["sensitivity"] == "legacy_unclassified"
    assert migrated_row["source"] == "legacy"


def test_memory_metadata_round_trip(repository):
    record = create_record().model_copy(
        update={
            "sensitivity": MemorySensitivity.PUBLIC,
            "source": MemorySource.SYSTEM,
        }
    )

    repository.save(record)
    retrieved = repository.get(record.task_id)

    assert retrieved is not None
    assert retrieved.sensitivity == MemorySensitivity.PUBLIC
    assert retrieved.source == MemorySource.SYSTEM


@pytest.mark.parametrize("limit", [1, 10, 100])
def test_recent_memory_accepts_valid_limits(repository, limit):
    assert repository.get_recent(limit=limit) == []


@pytest.mark.parametrize("limit", [0, -1, 101])
def test_recent_memory_rejects_out_of_range_limits(repository, limit):
    with pytest.raises(ValueError, match="between 1 and 100"):
        repository.get_recent(limit=limit)


@pytest.mark.parametrize("limit", [True, False, 1.5, "10", None])
def test_recent_memory_rejects_non_integer_limits(repository, limit):
    with pytest.raises(TypeError, match="must be an integer"):
        repository.get_recent(limit=limit)

def test_filter_recent_memories_by_intent(repository):
    first = create_record()
    second = create_record().model_copy(
        update={"intent": "code_review"}
    )

    repository.save(first)
    repository.save(second)

    results = repository.get_recent(intent="file_analysis")

    assert len(results) == 1
    assert results[0].task_id == first.task_id


def test_filter_recent_memories_by_status(repository):
    completed = create_record()
    failed = create_record().model_copy(
        update={"status": MemoryStatus.FAILED}
    )

    repository.save(completed)
    repository.save(failed)

    results = repository.get_recent(status=MemoryStatus.FAILED)

    assert len(results) == 1
    assert results[0].task_id == failed.task_id


def test_filter_recent_memories_by_agent(repository):
    first = create_record()
    second = create_record().model_copy(
        update={"agent_name": "CodeReviewAgent"}
    )

    repository.save(first)
    repository.save(second)

    results = repository.get_recent(agent_name="CodeReviewAgent")

    assert len(results) == 1
    assert results[0].task_id == second.task_id

def test_get_recent_combines_all_filters(repository):
    matching = create_record().model_copy(
        update={
            "intent": "file_analysis",
            "status": MemoryStatus.COMPLETED,
            "agent_name": "FileAnalysisAgent",
        }
    )

    wrong_intent = create_record().model_copy(
        update={"intent": "code_review"}
    )

    wrong_status = create_record().model_copy(
        update={"status": MemoryStatus.FAILED}
    )

    wrong_agent = create_record().model_copy(
        update={"agent_name": "CodeReviewAgent"}
    )

    for record in (matching, wrong_intent, wrong_status, wrong_agent):
        repository.save(record)

    results = repository.get_recent(
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
    )

    assert results == [matching]
@pytest.mark.parametrize(
    ("filters", "error"),
    [
        ({"intent": 123}, TypeError),
        ({"intent": ""}, ValueError),
        ({"status": "completed"}, TypeError),
        ({"agent_name": 123}, TypeError),
        ({"agent_name": " "}, ValueError),
    ],
)
def test_get_recent_rejects_invalid_filters(repository, filters, error):
    with pytest.raises(error):
        repository.get_recent(**filters)
def test_recent_memories_support_offset_pagination(repository):
    records = [create_record() for _ in range(5)]

    for record in records:
        repository.save(record)

    first_page = repository.get_recent(limit=2, offset=0)
    second_page = repository.get_recent(limit=2, offset=2)
    third_page = repository.get_recent(limit=2, offset=4)

    expected = list(reversed(records))

    assert [record.task_id for record in first_page] == [
        record.task_id for record in expected[:2]
    ]
    assert [record.task_id for record in second_page] == [
        record.task_id for record in expected[2:4]
    ]
    assert [record.task_id for record in third_page] == [
        record.task_id for record in expected[4:]
    ]