
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import uuid4

from app.memory.context_builder import MemoryContextBuilder
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemoryStatus,
)


def create_archived_record():
    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Historical planning task",
        created_at=datetime.now(timezone.utc),
        lifecycle_status=MemoryLifecycleStatus.ARCHIVED,
        archived_at=datetime.now(timezone.utc),
    )


def test_historical_context_retrieves_archived_memories():
    manager = MagicMock()
    record = create_archived_record()

    manager.get_archived_tasks.return_value = [record]

    builder = MemoryContextBuilder(manager)
    current_task_id = uuid4()

    context = builder.build_historical_context(
        task_id=current_task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 1
    assert context.memories[0].source_task_id == record.task_id
    assert (
        context.memories[0].lifecycle_status
        == MemoryLifecycleStatus.ARCHIVED
    )

    manager.get_archived_tasks.assert_called_once_with(
        limit=50,
        requesting_agent="PlanningAgent",
        intent="PLAN_TASK",
    )


def test_historical_context_excludes_current_task():
    manager = MagicMock()
    record = create_archived_record()

    manager.get_archived_tasks.return_value = [record]

    builder = MemoryContextBuilder(manager)

    context = builder.build_historical_context(
        task_id=record.task_id,
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_historical_context_respects_limit():
    manager = MagicMock()
    records = [create_archived_record() for _ in range(4)]

    manager.get_archived_tasks.return_value = records

    builder = MemoryContextBuilder(manager)

    context = builder.build_historical_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
        limit=2,
    )

    assert len(context.memories) == 2


def test_historical_context_does_not_record_active_usage():
    manager = MagicMock()
    manager.get_archived_tasks.return_value = [
        create_archived_record()
    ]

    builder = MemoryContextBuilder(manager)

    builder.build_historical_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    manager.record_usage.assert_not_called()


def test_normal_context_does_not_retrieve_archived_memories():
    manager = MagicMock()
    manager.get_recent_tasks.return_value = []

    builder = MemoryContextBuilder(manager)

    builder.build_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    manager.get_recent_tasks.assert_called_once()
    manager.get_archived_tasks.assert_not_called()
