from app.bootstrap import create_coordinator
from app.memory.schemas import MemorySensitivity, MemorySource
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.verification_agent import VerificationAgent
from datetime import datetime, timezone
from uuid import uuid4

from app.core.config import settings
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)

def test_create_coordinator_initializes_application():
    coordinator = create_coordinator()

    assert coordinator is not None
    assert coordinator.memory_manager is not None

    agents = coordinator.registry.list_agents()

    assert agents == [
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    ]

    assert isinstance(
        coordinator.registry.get("FileAnalysisAgent"),
        FileAnalysisAgent,
    )
    assert isinstance(
        coordinator.registry.get("PlanningAgent"),
        PlanningAgent,
    )
    assert isinstance(
        coordinator.registry.get("VerificationAgent"),
        VerificationAgent,
    )
def test_memory_persists_after_coordinator_restart(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "memory.db"

    monkeypatch.setattr(
        settings,
        "database_path",
        database_path,
    )

    # First application session.
    first_coordinator = create_coordinator()

    record = EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Successfully analyzed a project folder.",
        created_at=datetime.now(timezone.utc),
    )

    first_coordinator.memory_manager.remember_task(record)

    # Simulate application restart.
    second_coordinator = create_coordinator()

    retrieved = second_coordinator.memory_manager.get_task(
        record.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert retrieved == record

def test_multiple_memories_preserve_metadata_after_restart(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "memory.db"

    monkeypatch.setattr(settings, "database_path", database_path)

    first_coordinator = create_coordinator()

    records = [
        (
            EpisodicMemoryRecord(
                task_id=uuid4(),
                intent="file_analysis",
                status=MemoryStatus.COMPLETED,
                agent_name="FileAnalysisAgent",
                summary="Public memory record.",
                created_at=datetime.now(timezone.utc),
            ),
            MemorySensitivity.PUBLIC,
            MemorySource.SYSTEM,
        ),
        (
            EpisodicMemoryRecord(
                task_id=uuid4(),
                intent="plan_task",
                status=MemoryStatus.FAILED,
                agent_name="PlanningAgent",
                summary="Internal memory record.",
                created_at=datetime.now(timezone.utc),
            ),
            MemorySensitivity.INTERNAL,
            MemorySource.COORDINATOR,
        ),
    ]

    for record, sensitivity, source in records:
        first_coordinator.memory_manager.remember_task(
            record,
            sensitivity=sensitivity,
            source=source,
        )

    # Simulate application restart.
    second_coordinator = create_coordinator()

    for record, sensitivity, source in records:
        retrieved = second_coordinator.memory_manager.get_task(
            record.task_id,
            requesting_agent="CoordinatorAgent",
        )

        assert retrieved is not None
        assert retrieved.sensitivity == sensitivity
        assert retrieved.source == source
        assert retrieved.summary == record.summary
        assert retrieved.status == record.status
import sqlite3

import pytest

from app.bootstrap import create_coordinator
from app.core.config import settings


def test_coordinator_rejects_corrupted_database(tmp_path, monkeypatch):
    database_path = tmp_path / "corrupted.db"
    corrupted_content = b"This is not a valid SQLite database"
    database_path.write_bytes(corrupted_content)

    monkeypatch.setattr(settings, "database_path", database_path)

    with pytest.raises(sqlite3.DatabaseError):
        create_coordinator()

    assert database_path.read_bytes() == corrupted_content