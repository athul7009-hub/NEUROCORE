
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.procedural_policy import ProceduralMemoryPolicy
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
def procedural_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "procedural_identity.db")
    database.initialize()

    repository = ProceduralMemoryRepository(database)
    repository.initialize()

    return ProceduralMemoryManager(
        repository,
        ProceduralMemoryPolicy(),
    )


def create_record(procedure_id, status):
    now = datetime.now(timezone.utc)

    return ProceduralMemoryRecord(
        procedure_id=procedure_id,
        name="Create Python project",
        description="Create a basic Python project structure.",
        when_to_use="When starting a new Python application.",
        steps=[
            ProceduralMemoryStep(
                step_number=1,
                instruction="Create the project directory.",
            )
        ],
        confidence=0.95,
        status=status,
        sensitivity=MemorySensitivity.INTERNAL,
        source=ProceduralMemorySource.AGENT,
        created_at=now,
        updated_at=now,
    )


def test_inspect_candidate_identity(procedural_manager):
    procedure_id = uuid4()

    procedural_manager.remember(
        create_record(procedure_id, ProceduralMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    result = procedural_manager.inspect_identity(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == ProceduralMemoryStatus.CANDIDATE


def test_inspect_validated_identity(procedural_manager):
    procedure_id = uuid4()

    procedural_manager.remember(
        create_record(procedure_id, ProceduralMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    assert procedural_manager.validate(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    result = procedural_manager.inspect_identity(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == ProceduralMemoryStatus.VALIDATED


def test_inspect_deprecated_identity(procedural_manager):
    procedure_id = uuid4()

    procedural_manager.remember(
        create_record(procedure_id, ProceduralMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    assert procedural_manager.deprecate(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    result = procedural_manager.inspect_identity(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == ProceduralMemoryStatus.DEPRECATED


def test_inspect_nonexistent_identity(procedural_manager):
    result = procedural_manager.inspect_identity(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    )

    assert result is None


def test_non_coordinator_cannot_inspect_identity(procedural_manager):
    with pytest.raises(PermissionError):
        procedural_manager.inspect_identity(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_invalid_procedure_id_is_rejected(procedural_manager):
    with pytest.raises(TypeError):
        procedural_manager.inspect_identity(
            "not-a-uuid",
            requesting_agent="CoordinatorAgent",
        )


def test_unauthorized_requester_cannot_check_existence(
    procedural_manager,
):
    procedure_id = uuid4()

    procedural_manager.remember(
        create_record(procedure_id, ProceduralMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    with pytest.raises(PermissionError):
        procedural_manager.inspect_identity(
            procedure_id,
            requesting_agent="FileAnalysisAgent",
        )


def test_identity_inspection_returns_status_not_record(
    procedural_manager,
):
    procedure_id = uuid4()

    procedural_manager.remember(
        create_record(procedure_id, ProceduralMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    result = procedural_manager.inspect_identity(
        procedure_id,
        requesting_agent="CoordinatorAgent",
    )

    assert isinstance(result, ProceduralMemoryStatus)
    assert not isinstance(result, ProceduralMemoryRecord)
