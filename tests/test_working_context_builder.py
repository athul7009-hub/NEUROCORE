
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.memory.working_context_builder import (
    WorkingMemoryContextBuilder,
)
from app.memory.working_manager import WorkingMemoryManager
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)

@pytest.fixture
def manager():
    repository = MagicMock()
    working_manager = WorkingMemoryManager(repository=repository)

    working_manager.search = MagicMock(
        wraps=working_manager.search
    )

    return working_manager


@pytest.fixture
def builder(manager):
    return WorkingMemoryContextBuilder(manager)


@pytest.fixture
def task_id():
    return uuid4()


@pytest.fixture
def working_record(task_id):
    now = datetime.now(timezone.utc)

    return WorkingMemoryRecord(
        task_id=task_id,
        key="file_observation",
        entry_type=WorkingMemoryEntryType.OBSERVATION,
        content={"filename": "report.txt"},
        source_agent="FileAnalysisAgent",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_build_context_retrieves_current_task_entries(
    builder,
    manager,
    task_id,
    working_record,
):
    manager.repository.search.return_value = [working_record]

    context = builder.build_context(
        task_id=task_id,
        recipient_agent="PlanningAgent",
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "PlanningAgent"
    assert len(context.entries) == 1
    assert context.entries[0].key == "file_observation"


def test_build_context_uses_coordinator_for_retrieval(
    builder,
    manager,
    task_id,
):
    builder.build_context(
        task_id=task_id,
        recipient_agent="PlanningAgent",
    )

    manager.search.assert_called_once_with(
        requesting_agent="CoordinatorAgent",
        task_id=task_id,
        limit=builder.MAX_CONTEXT_ITEMS,
    )


def test_build_context_rejects_unauthorized_recipient(
    builder,
    task_id,
):
    with pytest.raises(PermissionError):
        builder.build_context(
            task_id=task_id,
            recipient_agent="UnknownAgent",
        )


def test_build_context_rejects_invalid_task_id(builder):
    with pytest.raises(TypeError):
        builder.build_context(
            task_id="invalid-task-id",
            recipient_agent="PlanningAgent",
        )


def test_build_context_returns_empty_context_when_no_entries(
    builder,
    manager,
    task_id,
):
    manager.repository.search.return_value = []

    context = builder.build_context(
        task_id=task_id,
        recipient_agent="PlanningAgent",
    )

    assert context.entries == []


def test_build_context_limits_entries(
    builder,
    manager,
    task_id,
    working_record,
):
    manager.repository.search.return_value = [
        working_record
    ] * 25

    context = builder.build_context(
        task_id=task_id,
        recipient_agent="PlanningAgent",
    )

    assert len(context.entries) <= builder.MAX_CONTEXT_ITEMS


def test_builder_propagates_authorization_failure(
    builder,
    manager,
    task_id,
):
    manager.search.side_effect = PermissionError(
        "Unauthorized working memory access."
    )

    with pytest.raises(PermissionError):
        builder.build_context(
            task_id=task_id,
            recipient_agent="PlanningAgent",
        )
