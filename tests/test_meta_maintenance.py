
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.meta_maintenance import MetaMemoryMaintenanceManager
from app.memory.meta_manager import MetaMemoryManager
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryType,
)


@pytest.fixture
def manager(tmp_path):
    from app.memory.database import SQLiteDatabase
    from app.memory.repositories.meta_memory import MetaMemoryRepository

    database = SQLiteDatabase(tmp_path / "maintenance.db")
    repository = MetaMemoryRepository(database)
    instance = MetaMemoryManager(repository)
    instance.initialize()
    return instance


@pytest.fixture
def maintenance(manager):
    return MetaMemoryMaintenanceManager(manager)


def store_records(manager, count):
    records = []

    for index in range(count):
        record = MetaMemoryRecord(
            memory_type=MetaMemoryType.EPISODIC,
            memory_id=f"memory-{index}",
        )
        manager.remember(
            record,
            requesting_agent="CoordinatorAgent",
        )
        records.append(record)

    return records


def test_assesses_unassessed_records(manager, maintenance):
    records = store_records(manager, 3)

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
    )

    assert report.total_examined == 3
    assert report.assessed == 3
    assert report.skipped == 0
    assert report.failed == 0

    for record in records:
        stored = manager.get(
            record.meta_id,
            requesting_agent="CoordinatorAgent",
        )
        assert stored.last_assessed_at is not None


def test_skips_recently_assessed_records(manager, maintenance):
    records = store_records(manager, 2)

    for record in records:
        manager.assess_and_persist(
            record.meta_id,
            requesting_agent="CoordinatorAgent",
        )

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
    )

    assert report.total_examined == 2
    assert report.assessed == 0
    assert report.skipped == 2
    assert report.failed == 0


def test_reassesses_old_assessments(manager, maintenance):
    records = store_records(manager, 2)
    old_time = datetime.now(timezone.utc) - timedelta(days=100)

    for record in records:
        manager.repository.update_assessment(
            record.meta_id,
            quality_score=0.5,
            assessment_confidence=0.5,
            staleness_status=manager.assessment_engine.assess(
                record,
                now=old_time,
            ).staleness_status,
            assessed_at=old_time,
        )

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
    )

    assert report.assessed == 2
    assert report.skipped == 0


def test_continues_after_individual_assessment_failure(
    manager,
    maintenance,
    monkeypatch,
):
    records = store_records(manager, 3)
    original = manager.assess_and_persist
    failed_id = records[1].meta_id

    def failing_assessment(meta_id, **kwargs):
        if meta_id == failed_id:
            raise RuntimeError("Simulated assessment failure")
        return original(meta_id, **kwargs)

    monkeypatch.setattr(
        manager,
        "assess_and_persist",
        failing_assessment,
    )

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
    )

    assert report.total_examined == 3
    assert report.assessed == 2
    assert report.failed == 1
    assert report.failed_meta_ids == [failed_id]


def test_respects_batch_size_and_paginates(manager, maintenance):
    store_records(manager, 5)

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
        batch_size=2,
    )

    assert report.total_examined == 5
    assert report.assessed == 5
    assert report.failed == 0


def test_enforces_maximum_records_per_run(manager, maintenance):
    store_records(manager, 105)

    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
        batch_size=50,
    )

    assert report.total_examined == 100
    assert report.assessed == 100


def test_rejects_unauthorized_requester(maintenance):
    with pytest.raises(PermissionError):
        maintenance.maintain(
            requesting_agent="PlanningAgent",
        )


@pytest.mark.parametrize("batch_size", [0, 101, -1])
def test_rejects_invalid_batch_size(maintenance, batch_size):
    with pytest.raises(ValueError):
        maintenance.maintain(
            requesting_agent="CoordinatorAgent",
            batch_size=batch_size,
        )


def test_rejects_non_integer_batch_size(maintenance):
    with pytest.raises(TypeError):
        maintenance.maintain(
            requesting_agent="CoordinatorAgent",
            batch_size=2.5,
        )


def test_rejects_naive_assessment_time(maintenance):
    with pytest.raises(ValueError):
        maintenance.maintain(
            requesting_agent="CoordinatorAgent",
            now=datetime.now(),
        )


def test_rejects_future_assessment_time(maintenance):
    future = datetime.now(timezone.utc) + timedelta(days=1)

    with pytest.raises(ValueError):
        maintenance.maintain(
            requesting_agent="CoordinatorAgent",
            now=future,
        )


def test_returns_empty_report_when_no_records_exist(
    maintenance,
):
    report = maintenance.maintain(
        requesting_agent="CoordinatorAgent",
    )

    assert report.total_examined == 0
    assert report.assessed == 0
    assert report.skipped == 0
    assert report.failed == 0
