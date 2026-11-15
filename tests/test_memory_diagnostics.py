
import pytest

from app.memory.database import SQLiteDatabase
from app.memory.diagnostics import MemoryDiagnostics
from app.memory.repositories.episodic_memory import EpisodicMemoryRepository
from app.memory.repositories.meta_conflict import MetaMemoryConflictRepository
from app.memory.repositories.meta_memory import MetaMemoryRepository
from app.memory.repositories.procedural_memory import ProceduralMemoryRepository
from app.memory.repositories.prospective_memory import ProspectiveMemoryRepository
from app.memory.repositories.semantic_memory import SemanticMemoryRepository
from app.memory.repositories.working_memory import WorkingMemoryRepository
from datetime import datetime, timezone
from uuid import uuid4

from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemoryStatus,
)
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)

@pytest.fixture
def diagnostics(tmp_path):
    database = SQLiteDatabase(tmp_path / "diagnostics.db")
    database.initialize()

    repositories = [
        EpisodicMemoryRepository(database),
        SemanticMemoryRepository(database),
        ProceduralMemoryRepository(database),
        WorkingMemoryRepository(database),
        ProspectiveMemoryRepository(database),
        MetaMemoryRepository(database),
        MetaMemoryConflictRepository(database),
    ]

    for repository in repositories:
        repository.initialize()

    return MemoryDiagnostics(database)


def test_inspect_returns_all_memory_tables(diagnostics):
    report = diagnostics.inspect()

    assert set(report.memory_tables) == {
        "episodic",
        "semantic",
        "procedural",
        "working",
        "prospective",
        "meta",
        "meta_conflicts",
    }


def test_empty_database_has_zero_records(diagnostics):
    report = diagnostics.inspect()

    for table in report.memory_tables.values():
        assert table.total_records == 0
        assert table.status_counts == {}


def test_database_integrity_is_reported(diagnostics):
    report = diagnostics.inspect()

    assert report.database_integrity is True
    assert report.foreign_key_integrity is True


def test_diagnostics_report_is_read_only(diagnostics):
    before = diagnostics.inspect()
    after = diagnostics.inspect()

    assert after == before

def test_reports_semantic_status_counts(diagnostics):
    repository = SemanticMemoryRepository(diagnostics.database)

    repository.save(
        SemanticMemoryRecord(
            subject="Python",
            predicate="is",
            object="A programming language",
            source=SemanticMemorySource.USER,
            status=SemanticMemoryStatus.CANDIDATE,
        )
    )

    repository.save(
        SemanticMemoryRecord(
            subject="SQLite",
            predicate="is",
            object="A database engine",
            source=SemanticMemorySource.USER,
            status=SemanticMemoryStatus.VALIDATED,
            validated_at=datetime.now(timezone.utc),
            validated_by="CoordinatorAgent",
        )
    )

    report = diagnostics.inspect()
    semantic = report.memory_tables["semantic"]

    assert semantic.total_records == 2
    assert semantic.status_counts == {
        "candidate": 1,
        "validated": 1,
    }


def test_reports_episodic_lifecycle_counts(diagnostics):
    repository = EpisodicMemoryRepository(diagnostics.database)
    now = datetime.now(timezone.utc)

    repository.save(
        EpisodicMemoryRecord(
            task_id=uuid4(),
            intent="PLAN_TASK",
            status=MemoryStatus.COMPLETED,
            agent_name="PlanningAgent",
            summary="Test completed task",
            created_at=now,
            lifecycle_status=MemoryLifecycleStatus.ACTIVE,
        )
    )

    report = diagnostics.inspect()
    episodic = report.memory_tables["episodic"]

    assert episodic.total_records == 1
    assert episodic.status_counts == {"active": 1}
