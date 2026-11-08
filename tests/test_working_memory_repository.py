
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.working_memory import (
    WorkingMemoryRepository,
)
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


@pytest.fixture
def repository(tmp_path):
    database = SQLiteDatabase(tmp_path / "working_memory.db")
    database.initialize()

    repo = WorkingMemoryRepository(database)
    repo.initialize()

    return repo



def create_record(
    *,
    task_id=None,
    entry_id=None,
    key="test_entry",
    entry_type=WorkingMemoryEntryType.OBSERVATION,
    content=None,
    source_agent="PlanningAgent",
    expires_in=3600,
):
    now = datetime.now(timezone.utc)

    created_at = (
        now
        if expires_in > 0
        else now + timedelta(seconds=expires_in - 1)
    )

    return WorkingMemoryRecord(
        entry_id=entry_id or uuid4(),
        task_id=task_id or uuid4(),
        key=key,
        entry_type=entry_type,
        content=content or {"result": "success"},
        source_agent=source_agent,
        created_at=created_at,
        updated_at=created_at,
        expires_at=now + timedelta(seconds=expires_in),
    )



def test_initialize_creates_working_memory_table(repository):
    with repository.database.connection() as connection:
        row = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
              AND name = 'working_memory'
            """
        ).fetchone()

    assert row is not None


def test_save_and_get_record(repository):
    record = create_record()

    repository.save(record)

    retrieved = repository.get(
        record.entry_id,
        record.task_id,
    )

    assert retrieved is not None
    assert retrieved.entry_id == record.entry_id
    assert retrieved.task_id == record.task_id
    assert retrieved.content == record.content
    assert retrieved.key == record.key


def test_get_returns_none_for_unknown_entry(repository):
    result = repository.get(uuid4(), uuid4())

    assert result is None


def test_get_enforces_task_isolation(repository):
    record = create_record()
    repository.save(record)

    result = repository.get(
        record.entry_id,
        uuid4(),
    )

    assert result is None


def test_search_returns_entries_for_task_only(repository):
    task_id = uuid4()

    first = create_record(task_id=task_id, key="first")
    second = create_record(task_id=task_id, key="second")
    unrelated = create_record(key="unrelated")

    repository.save(first)
    repository.save(second)
    repository.save(unrelated)

    results = repository.search(task_id=task_id)

    assert len(results) == 2
    assert {record.key for record in results} == {
        "first",
        "second",
    }


def test_search_filters_by_entry_type(repository):
    task_id = uuid4()

    observation = create_record(
        task_id=task_id,
        entry_type=WorkingMemoryEntryType.OBSERVATION,
    )
    note = create_record(
        task_id=task_id,
        entry_type=WorkingMemoryEntryType.AGENT_NOTE,
    )

    repository.save(observation)
    repository.save(note)

    results = repository.search(
        task_id=task_id,
        entry_type=WorkingMemoryEntryType.AGENT_NOTE,
    )

    assert len(results) == 1
    assert results[0].entry_id == note.entry_id


def test_search_filters_by_source_agent(repository):
    task_id = uuid4()

    planning = create_record(
        task_id=task_id,
        source_agent="PlanningAgent",
    )
    verification = create_record(
        task_id=task_id,
        source_agent="VerificationAgent",
    )

    repository.save(planning)
    repository.save(verification)

    results = repository.search(
        task_id=task_id,
        source_agent="VerificationAgent",
    )

    assert len(results) == 1
    assert results[0].source_agent == "VerificationAgent"


def test_search_respects_limit(repository):
    task_id = uuid4()

    for index in range(5):
        repository.save(
            create_record(task_id=task_id, key=f"entry_{index}")
        )

    results = repository.search(task_id=task_id, limit=2)

    assert len(results) == 2


def test_search_respects_offset(repository):
    task_id = uuid4()

    records = [
        create_record(task_id=task_id, key=f"entry_{index}")
        for index in range(3)
    ]

    for record in records:
        repository.save(record)

    all_results = repository.search(task_id=task_id)
    offset_results = repository.search(task_id=task_id, offset=1)

    assert len(offset_results) == 2
    assert offset_results[0].entry_id == all_results[1].entry_id


def test_search_excludes_expired_entries(repository):
    task_id = uuid4()

    expired = create_record(
        task_id=task_id,
        expires_in=-1,
    )
    active = create_record(task_id=task_id)

    repository.save(expired)
    repository.save(active)

    results = repository.search(task_id=task_id)

    assert len(results) == 1
    assert results[0].entry_id == active.entry_id


def test_get_excludes_expired_entries(repository):
    expired = create_record(expires_in=-1)
    repository.save(expired)

    result = repository.get(
        expired.entry_id,
        expired.task_id,
    )

    assert result is None


def test_update_changes_existing_record(repository):
    record = create_record()
    repository.save(record)

    updated = record.model_copy(
        update={
            "key": "updated_key",
            "content": {"result": "updated"},
            "updated_at": datetime.now(timezone.utc)
            + timedelta(seconds=1),
        }
    )

    assert repository.update(updated) is True

    retrieved = repository.get(
        record.entry_id,
        record.task_id,
    )

    assert retrieved is not None
    assert retrieved.key == "updated_key"
    assert retrieved.content == {"result": "updated"}
    assert retrieved.created_at == record.created_at


def test_update_returns_false_for_unknown_entry(repository):
    record = create_record()

    assert repository.update(record) is False


def test_update_cannot_cross_task_boundaries(repository):
    record = create_record()
    repository.save(record)

    forged = record.model_copy(
        update={"task_id": uuid4()}
    )

    assert repository.update(forged) is False


def test_delete_expired_removes_only_expired_entries(repository):
    task_id = uuid4()

    expired = create_record(
        task_id=task_id,
        expires_in=-1,
    )
    active = create_record(task_id=task_id)

    repository.save(expired)
    repository.save(active)

    deleted_count = repository.delete_expired()

    assert deleted_count == 1
    assert repository.get(
        expired.entry_id,
        task_id,
    ) is None
    assert repository.get(
        active.entry_id,
        task_id,
    ) is not None


def test_delete_expired_returns_zero_when_nothing_expired(repository):
    repository.save(create_record())

    assert repository.delete_expired() == 0


@pytest.mark.parametrize("limit", [0, 101, -1])
def test_search_rejects_invalid_limit(repository, limit):
    with pytest.raises(ValueError):
        repository.search(task_id=uuid4(), limit=limit)


@pytest.mark.parametrize("limit", [True, 1.5, "10"])
def test_search_rejects_non_integer_limit(repository, limit):
    with pytest.raises(TypeError):
        repository.search(task_id=uuid4(), limit=limit)


@pytest.mark.parametrize("offset", [-1, -10])
def test_search_rejects_negative_offset(repository, offset):
    with pytest.raises(ValueError):
        repository.search(task_id=uuid4(), offset=offset)


@pytest.mark.parametrize("offset", [True, 1.5, "1"])
def test_search_rejects_non_integer_offset(repository, offset):
    with pytest.raises(TypeError):
        repository.search(task_id=uuid4(), offset=offset)


def test_search_rejects_invalid_task_id(repository):
    with pytest.raises(TypeError):
        repository.search(task_id="invalid")


def test_search_rejects_invalid_entry_type(repository):
    with pytest.raises(TypeError):
        repository.search(
            task_id=uuid4(),
            entry_type="observation",
        )


def test_search_rejects_empty_source_agent(repository):
    with pytest.raises(ValueError):
        repository.search(
            task_id=uuid4(),
            source_agent=" ",
        )

def test_update_cannot_revive_expired_entry(repository):
    record = create_record(expires_in=-1)
    repository.save(record)

    revived = record.model_copy(
        update={
            "updated_at": datetime.now(timezone.utc),
            "expires_at": datetime.now(timezone.utc) + timedelta(hours=1),
        }
    )

    assert repository.update(revived) is False


def test_update_cannot_change_original_owner(repository):
    record = create_record(source_agent="PlanningAgent")
    repository.save(record)

    forged = record.model_copy(
        update={
            "source_agent": "VerificationAgent",
            "updated_at": datetime.now(timezone.utc) + timedelta(seconds=1),
        }
    )

    assert repository.update(forged) is False

    retrieved = repository.get(record.entry_id, record.task_id)

    assert retrieved is not None
    assert retrieved.source_agent == "PlanningAgent"


def test_update_rejects_backdated_timestamp(repository):
    record = create_record()
    repository.save(record)

    newer_timestamp = record.created_at + timedelta(seconds=2)

    newer_record = record.model_copy(
        update={"updated_at": newer_timestamp}
    )

    assert repository.update(newer_record) is True

    older_record = record.model_copy(
        update={
            "updated_at": record.created_at + timedelta(seconds=1),
            "content": {"result": "stale update"},
        }
    )

    assert repository.update(older_record) is False

    retrieved = repository.get(record.entry_id, record.task_id)

    assert retrieved is not None
    assert retrieved.updated_at == newer_timestamp
    assert retrieved.content == record.content

from concurrent.futures import ThreadPoolExecutor


def test_concurrent_saves_preserve_all_entries(repository):
    task_id = uuid4()
    records = [
        create_record(task_id=task_id, key=f"entry_{index}")
        for index in range(20)
    ]

    with ThreadPoolExecutor(max_workers=5) as executor:
        list(executor.map(repository.save, records))

    results = repository.search(task_id=task_id, limit=100)

    assert len(results) == 20
    assert {record.entry_id for record in results} == {
        record.entry_id for record in records
    }


def test_concurrent_reads_and_writes_preserve_task_isolation(repository):
    task_id = uuid4()
    unrelated_task_id = uuid4()

    initial = create_record(task_id=task_id)
    repository.save(initial)

    def write_entries():
        for index in range(10):
            repository.save(
                create_record(
                    task_id=task_id,
                    key=f"new_{index}",
                )
            )

    def read_entries():
        for _ in range(10):
            results = repository.search(task_id=task_id, limit=100)
            assert all(record.task_id == task_id for record in results)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(write_entries),
            executor.submit(read_entries),
            executor.submit(read_entries),
        ]

        for future in futures:
            future.result()

    assert len(repository.search(task_id=task_id, limit=100)) == 11
    assert repository.search(task_id=unrelated_task_id) == []

def test_working_memory_persists_across_repository_instances(
    repository,
    tmp_path,
):
    record = create_record()
    repository.save(record)

    new_database = SQLiteDatabase(tmp_path / "working_memory.db")
    new_repository = WorkingMemoryRepository(new_database)
    new_repository.initialize()

    retrieved = new_repository.get(
        record.entry_id,
        record.task_id,
    )

    assert retrieved is not None
    assert retrieved.entry_id == record.entry_id
    assert retrieved.content == record.content
    assert retrieved.source_agent == record.source_agent
