
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from unittest.mock import Mock

import pytest

from app.memory.context_builder import MemoryContextBuilder
from app.memory.manager import MemoryManager
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)
from app.memory.memory_policy import MemoryPolicy

@pytest.fixture
def memory_manager():
    manager = Mock(spec=MemoryManager)
    manager.policy = MemoryPolicy()
    return manager


@pytest.fixture
def builder(memory_manager):
    return MemoryContextBuilder(memory_manager)


@pytest.fixture
def current_task_id():
    return uuid4()


@pytest.fixture
def memory_records():
    now = datetime.now(timezone.utc)

    return [
        EpisodicMemoryRecord(
            task_id=uuid4(),
            intent="PLAN_TASK",
            status=MemoryStatus.COMPLETED,
            agent_name="PlanningAgent",
            summary="Created a project execution plan.",
            created_at=now,
            completed_at=now,
        ),
        EpisodicMemoryRecord(
            task_id=uuid4(),
            intent="PLAN_TASK",
            status=MemoryStatus.FAILED,
            agent_name="PlanningAgent",
            summary="Failed because the project directory was invalid.",
            created_at=now,
            completed_at=now,
        ),
    ]


def test_build_context_returns_relevant_memories(
    builder,
    memory_manager,
    current_task_id,
    memory_records,
):
    memory_manager.get_recent_tasks.return_value = memory_records

    context = builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 2
    assert context.task_id == current_task_id
    assert context.recipient_agent == "PlanningAgent"
    assert context.memories[0].summary == (
        "Created a project execution plan."
    )

    memory_manager.get_recent_tasks.assert_called_once_with(
        limit=50,
        requesting_agent="PlanningAgent",
        intent="PLAN_TASK",
    )


def test_build_context_excludes_current_task(
    builder,
    memory_manager,
    current_task_id,
):
    now = datetime.now(timezone.utc)

    record = EpisodicMemoryRecord(
        task_id=current_task_id,
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Current task.",
        created_at=now,
        completed_at=now,
    )

    memory_manager.get_recent_tasks.return_value = [record]

    context = builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_build_context_respects_memory_limit(
    builder,
    memory_manager,
    current_task_id,
    memory_records,
):
    memory_manager.get_recent_tasks.return_value = memory_records

    builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
        limit=3,
    )

    memory_manager.get_recent_tasks.assert_called_once_with(
        limit=50,
        requesting_agent="PlanningAgent",
        intent="PLAN_TASK",
    )


def test_build_context_returns_empty_context(
    builder,
    memory_manager,
    current_task_id,
):
    memory_manager.get_recent_tasks.return_value = []

    context = builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


@pytest.mark.parametrize(
    "task_id",
    ["invalid-id", None, 123],
)
def test_build_context_rejects_invalid_task_id(
    builder,
    task_id,
):
    with pytest.raises(TypeError):
        builder.build_context(
            task_id=task_id,
            intent="PLAN_TASK",
            recipient_agent="PlanningAgent",
        )


@pytest.mark.parametrize(
    "intent",
    ["", "   ", None, 123],
)
def test_build_context_rejects_invalid_intent(
    builder,
    current_task_id,
    intent,
):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=current_task_id,
            intent=intent,
            recipient_agent="PlanningAgent",
        )


@pytest.mark.parametrize(
    "recipient",
    ["", "   ", None, 123],
)
def test_build_context_rejects_invalid_recipient(
    builder,
    current_task_id,
    recipient,
):
    expected_exception = (
        TypeError if not isinstance(recipient, str) else ValueError
    )

    with pytest.raises(expected_exception):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent=recipient,
        )


@pytest.mark.parametrize(
    "limit",
    [0, -1, 11],
)
def test_build_context_rejects_out_of_range_limit(
    builder,
    current_task_id,
    limit,
):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent="PlanningAgent",
            limit=limit,
        )


@pytest.mark.parametrize(
    "limit",
    [True, 1.5, "5"],
)
def test_build_context_rejects_invalid_limit_type(
    builder,
    current_task_id,
    limit,
):
    with pytest.raises(TypeError):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent="PlanningAgent",
            limit=limit,
        )


def test_build_context_propagates_memory_authorization_failure(
    builder,
    memory_manager,
    current_task_id,
):
    memory_manager.get_recent_tasks.side_effect = PermissionError(
        "Unauthorized memory retrieval."
    )

    with pytest.raises(PermissionError):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent="UntrustedAgent",
        )


def test_build_context_retrieves_larger_candidate_pool(
    builder,
    memory_manager,
    current_task_id,
):
    memory_manager.get_recent_tasks.return_value = []

    builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
        objective="Analyze Python project dependencies",
    )

    memory_manager.get_recent_tasks.assert_called_once_with(
        limit=50,
        requesting_agent="PlanningAgent",
        intent="PLAN_TASK",
    )


def test_build_context_selects_older_relevant_memory(
    builder,
    memory_manager,
    current_task_id,
):
    now = datetime.now(timezone.utc)

    recent_irrelevant = EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Prepare restaurant inventory database.",
        created_at=now,
        completed_at=now,
    )

    older_relevant = EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Analyze Python project dependencies.",
        created_at=now - timedelta(days=60),
        completed_at=now - timedelta(days=60),
    )

    memory_manager.get_recent_tasks.return_value = [
        recent_irrelevant,
        older_relevant,
    ]

    context = builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
        objective="Analyze Python project dependencies",
    )

    assert len(context.memories) == 1
    assert context.memories[0].summary == (
        "Analyze Python project dependencies."
    )


def test_build_context_never_exceeds_maximum_memories(
    builder,
    memory_manager,
    current_task_id,
):
    now = datetime.now(timezone.utc)

    records = [
        EpisodicMemoryRecord(
            task_id=uuid4(),
            intent="PLAN_TASK",
            status=MemoryStatus.COMPLETED,
            agent_name="PlanningAgent",
            summary="Analyze Python project dependencies.",
            created_at=now - timedelta(days=index),
            completed_at=now - timedelta(days=index),
        )
        for index in range(15)
    ]

    memory_manager.get_recent_tasks.return_value = records

    context = builder.build_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
        objective="Analyze Python project dependencies",
    )

    assert len(context.memories) <= 10
@pytest.mark.parametrize(
    "objective",
    ["", "   ", 123],
)
def test_build_context_rejects_invalid_objective(
    builder,
    current_task_id,
    objective,
):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent="PlanningAgent",
            objective=objective,
        )


def test_build_context_propagates_database_failure(
    builder,
    memory_manager,
    current_task_id,
):
    import sqlite3

    memory_manager.get_recent_tasks.side_effect = (
        sqlite3.OperationalError("Database unavailable.")
    )

    with pytest.raises(sqlite3.OperationalError):
        builder.build_context(
            task_id=current_task_id,
            intent="PLAN_TASK",
            recipient_agent="PlanningAgent",
        )