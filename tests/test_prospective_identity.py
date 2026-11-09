
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
)
from app.memory.prospective_manager import ProspectiveMemoryManager
from app.memory.repositories.prospective_memory import (
    ProspectiveMemoryRepository,
)
from app.memory.prospective_schemas import (
    ProspectiveMemoryRecord,
    ProspectiveMemoryStatus,
    ProspectiveMemorySource,
    ProspectiveTriggerType,
)


COORDINATOR = "CoordinatorAgent"
UNAUTHORIZED_AGENT = "FileAnalysisAgent"


@pytest.fixture
def setup_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "prospective_identity.db")
    database.initialize()

    repository = ProspectiveMemoryRepository(database)
    repository.initialize()

    manager = ProspectiveMemoryManager(repository)

    return manager, repository


def create_record(
    *,
    is_protected=False,
):
    now = datetime.now(timezone.utc)

    return ProspectiveMemoryRecord(
        title="Test reminder",
        description="Test prospective memory description",
        action="Perform the test action",
        trigger_type=ProspectiveTriggerType.MANUAL,
        source=ProspectiveMemorySource.AGENT,
        source_agent=COORDINATOR,
        created_at=now,
        updated_at=now,
        is_protected=is_protected,
    )


def store_record(manager, record):
    manager.remember(
        record,
        requesting_agent=COORDINATOR,
    )
    return record


def test_inspect_pending_memory_returns_available(setup_manager):
    manager, _ = setup_manager
    record = store_record(manager, create_record())

    result = manager.inspect_identity(
        record.memory_id,
        requesting_agent=COORDINATOR,
    )

    assert isinstance(result, MemoryIdentityAssessment)
    assert result.exists is True
    assert result.memory_id == record.memory_id
    assert result.lifecycle_status == "pending"
    assert result.availability == MemoryIdentityAvailability.AVAILABLE


def test_inspect_protected_memory_returns_available(setup_manager):
    manager, _ = setup_manager
    record = store_record(
        manager,
        create_record(is_protected=True),
    )

    result = manager.inspect_identity(
        record.memory_id,
        requesting_agent=COORDINATOR,
    )

    assert result.exists is True
    assert result.lifecycle_status == "pending"
    assert result.availability == MemoryIdentityAvailability.AVAILABLE


@pytest.mark.parametrize(
    ("status", "expected_availability"),
    [
        (
            ProspectiveMemoryStatus.COMPLETED,
            MemoryIdentityAvailability.INACTIVE,
        ),
        (
            ProspectiveMemoryStatus.CANCELLED,
            MemoryIdentityAvailability.INACTIVE,
        ),
        (
            ProspectiveMemoryStatus.EXPIRED,
            MemoryIdentityAvailability.INACTIVE,
        ),
    ],
)
def test_inactive_memory_statuses(
    setup_manager,
    status,
    expected_availability,
):
    manager, repository = setup_manager
    record = store_record(manager, create_record())

    # Change only the lifecycle status for this identity test.
    with repository.database.connection() as connection:
        connection.execute(
            """
            UPDATE prospective_memory
            SET status = ?
            WHERE memory_id = ?
            """,
            (status.value, str(record.memory_id)),
        )

    result = manager.inspect_identity(
        record.memory_id,
        requesting_agent=COORDINATOR,
    )

    assert result.exists is True
    assert result.lifecycle_status == status.value
    assert result.availability == expected_availability


def test_inspect_nonexistent_memory_returns_not_found(setup_manager):
    manager, _ = setup_manager
    memory_id = uuid4()

    result = manager.inspect_identity(
        memory_id,
        requesting_agent=COORDINATOR,
    )

    assert result.exists is False
    assert result.memory_id == memory_id
    assert result.lifecycle_status is None
    assert result.availability == MemoryIdentityAvailability.NOT_FOUND


def test_non_coordinator_cannot_inspect_identity(setup_manager):
    manager, _ = setup_manager
    record = store_record(manager, create_record())

    with pytest.raises(PermissionError):
        manager.inspect_identity(
            record.memory_id,
            requesting_agent=UNAUTHORIZED_AGENT,
        )


def test_unauthorized_agent_cannot_check_memory_existence(setup_manager):
    manager, _ = setup_manager

    with pytest.raises(PermissionError):
        manager.inspect_identity(
            uuid4(),
            requesting_agent=UNAUTHORIZED_AGENT,
        )


def test_invalid_memory_id_raises_type_error(setup_manager):
    manager, _ = setup_manager

    with pytest.raises(TypeError):
        manager.inspect_identity(
            "not-a-uuid",
            requesting_agent=COORDINATOR,
        )


def test_identity_inspection_does_not_return_memory_content(setup_manager):
    manager, _ = setup_manager
    record = store_record(manager, create_record())

    result = manager.inspect_identity(
        record.memory_id,
        requesting_agent=COORDINATOR,
    )

    assert isinstance(result, MemoryIdentityAssessment)
    assert not isinstance(result, ProspectiveMemoryRecord)
    assert not hasattr(result, "description")
    assert not hasattr(result, "action")
