from app.bootstrap import create_coordinator
from app.memory.schemas import MemorySensitivity, MemorySource
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.verification_agent import VerificationAgent
from datetime import datetime, timezone
from uuid import uuid4
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryType,
)
from app.core.config import settings
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)
from uuid import uuid4
from pathlib import Path

from app.core.schemas import MessageType, TaskIntent, TaskRequest
from app.memory.schemas import MemoryStatus
from app.memory.database import SQLiteDatabase
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

def test_create_coordinator_initializes_meta_memory():
    coordinator = create_coordinator()

    assert coordinator.meta_memory_manager is not None

    memory_id = f"bootstrap-test-{uuid4()}"

    record = MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=memory_id,
    )

    coordinator.meta_memory_manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    retrieved = coordinator.meta_memory_manager.get_for_memory(
        MetaMemoryType.EPISODIC,
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert retrieved == record

def test_meta_memory_persists_after_coordinator_restart(
    tmp_path,
    monkeypatch,
):
    database_path = tmp_path / "meta_memory.db"

    monkeypatch.setattr(
        settings,
        "database_path",
        database_path,
    )

    first_coordinator = create_coordinator()

    record = MetaMemoryRecord(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id="semantic-memory-001",
        quality_score=0.9,
        assessment_confidence=0.85,
        last_assessed_at=datetime.now(timezone.utc),
    )

    first_coordinator.meta_memory_manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    second_coordinator = create_coordinator()

    retrieved = second_coordinator.meta_memory_manager.get_for_memory(
        MetaMemoryType.SEMANTIC,
        "semantic-memory-001",
        requesting_agent="CoordinatorAgent",
    )

    assert retrieved == record
def test_bootstrapped_coordinator_completes_file_analysis_task(
    tmp_path,
    monkeypatch,
):
    # Isolate application database.
    monkeypatch.setattr(
        settings,
        "database_path",
        tmp_path / "memory.db",
    )

    # Prepare a temporary folder with one file.
    scan_dir = tmp_path / "scan"
    scan_dir.mkdir()
    (scan_dir / "example.py").write_text(
        "print('NEUROCORE')",
        encoding="utf-8",
    )

    # Bypass only the profile-path restriction for this isolated test folder.
    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [scan_dir],
    )

    # Assemble the real application.
    coordinator = create_coordinator()

    task = TaskRequest(
        user_input="Analyze the test folder.",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": str(scan_dir)},
    )

    response = coordinator.handle_task(task)

    # Verify the real application workflow.
    assert response.task_id == task.task_id
    assert response.sender == "FileAnalysisAgent"
    assert response.message_type == MessageType.RESULT, response.payload

    # Verify that the completed task was recorded in episodic memory.
    record = coordinator.memory_manager.get_task(
        task.task_id,
        requesting_agent="CoordinatorAgent",
    )

    assert record is not None
    assert record.status == MemoryStatus.COMPLETED
    assert record.agent_name == "FileAnalysisAgent"
def test_create_coordinator_uses_supplied_database(tmp_path):
    database = SQLiteDatabase(tmp_path / "shared.db")

    coordinator = create_coordinator(database=database)

    assert coordinator.memory_manager.repository.database is database
    assert coordinator.semantic_memory_manager.repository.database is database
    assert coordinator.procedural_memory_manager.repository.database is database
    assert coordinator.working_memory_manager.repository.database is database
    assert coordinator.prospective_memory_manager.repository.database is database
    assert coordinator.meta_memory_manager.repository.database is database