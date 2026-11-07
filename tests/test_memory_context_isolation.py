from datetime import datetime, timezone
from uuid import uuid4

from app.memory.context_builder import MemoryContextBuilder
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemoryStatus,
)


def create_record(lifecycle_status):
    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Python application planning task",
        created_at=datetime.now(timezone.utc),
        lifecycle_status=lifecycle_status,
        archived_at=(
            datetime.now(timezone.utc)
            if lifecycle_status == MemoryLifecycleStatus.ARCHIVED
            else None
        ),
    )


def test_active_context_does_not_include_archived_memories():
    manager = __import__(
        "unittest.mock",
        fromlist=["MagicMock"],
    ).MagicMock()

    manager.get_recent_tasks.return_value = []

    builder = MemoryContextBuilder(manager)

    context = builder.build_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []
    manager.get_archived_tasks.assert_not_called()


def test_historical_context_does_not_include_active_memories():
    from unittest.mock import MagicMock

    manager = MagicMock()
    manager.get_archived_tasks.return_value = []

    builder = MemoryContextBuilder(manager)

    context = builder.build_historical_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []
    manager.get_recent_tasks.assert_not_called()


def test_restored_memory_is_available_only_in_active_context():
    from unittest.mock import MagicMock

    manager = MagicMock()
    record = create_record(MemoryLifecycleStatus.ACTIVE)

    manager.get_recent_tasks.return_value = [record]
    manager.get_archived_tasks.return_value = []

    builder = MemoryContextBuilder(manager)

    active_context = builder.build_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    historical_context = builder.build_historical_context(
        task_id=uuid4(),
        intent="PLAN_TASK",
        recipient_agent="PlanningAgent",
    )

    assert len(active_context.memories) == 1
    assert historical_context.memories == []