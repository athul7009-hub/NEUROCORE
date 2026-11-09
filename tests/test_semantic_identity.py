
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.schemas import MemorySensitivity
from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.semantic_policy import SemanticMemoryPolicy
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


@pytest.fixture
def semantic_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "semantic_identity.db")
    database.initialize()

    repository = SemanticMemoryRepository(database)
    repository.initialize()

    return SemanticMemoryManager(
        repository,
        SemanticMemoryPolicy(),
    )


def create_record(memory_id, status):
    now = datetime.now(timezone.utc)

    return SemanticMemoryRecord(
        memory_id=memory_id,
        subject="Python",
        predicate="is",
        object="A programming language",
        confidence=0.95,
        status=status,
        sensitivity=MemorySensitivity.INTERNAL,
        source=SemanticMemorySource.AGENT,
        created_at=now,
        updated_at=now,
    )


def test_inspect_candidate_identity(semantic_manager):
    memory_id = uuid4()

    semantic_manager.remember(
        create_record(memory_id, SemanticMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    result = semantic_manager.inspect_identity(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == SemanticMemoryStatus.CANDIDATE


def test_inspect_validated_identity(semantic_manager):
    memory_id = uuid4()

    semantic_manager.remember(
        create_record(memory_id, SemanticMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    assert semantic_manager.validate(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    result = semantic_manager.inspect_identity(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == SemanticMemoryStatus.VALIDATED


def test_inspect_deprecated_identity(semantic_manager):
    memory_id = uuid4()

    semantic_manager.remember(
        create_record(memory_id, SemanticMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    assert semantic_manager.deprecate(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    result = semantic_manager.inspect_identity(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == SemanticMemoryStatus.DEPRECATED


def test_inspect_nonexistent_identity(semantic_manager):
    result = semantic_manager.inspect_identity(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    )

    assert result is None


def test_non_coordinator_cannot_inspect_identity(semantic_manager):
    with pytest.raises(PermissionError):
        semantic_manager.inspect_identity(
            uuid4(),
            requesting_agent="PlanningAgent",
        )


def test_invalid_memory_id_is_rejected(semantic_manager):
    with pytest.raises(TypeError):
        semantic_manager.inspect_identity(
            "not-a-uuid",
            requesting_agent="CoordinatorAgent",
        )


def test_unauthorized_requester_cannot_check_existence(
    semantic_manager,
):
    memory_id = uuid4()

    semantic_manager.remember(
        create_record(memory_id, SemanticMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    with pytest.raises(PermissionError):
        semantic_manager.inspect_identity(
            memory_id,
            requesting_agent="FileAnalysisAgent",
        )


def test_identity_inspection_returns_status_not_record(
    semantic_manager,
):
    memory_id = uuid4()

    semantic_manager.remember(
        create_record(memory_id, SemanticMemoryStatus.CANDIDATE),
        requesting_agent="CoordinatorAgent",
    )

    result = semantic_manager.inspect_identity(
        memory_id,
        requesting_agent="CoordinatorAgent",
    )

    assert isinstance(result, SemanticMemoryStatus)
    assert not isinstance(result, SemanticMemoryRecord)
