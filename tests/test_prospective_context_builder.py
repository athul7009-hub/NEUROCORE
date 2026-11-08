from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.prospective_memory import (
    ProspectiveMemoryRepository,
)
from app.memory.prospective_context_builder import (
    ProspectiveMemoryContextBuilder,
)
from app.memory.prospective_manager import ProspectiveMemoryManager
from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveMemoryRecord,
    ProspectiveTriggerType,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "prospective_context.db")
    database.initialize()

    repository = ProspectiveMemoryRepository(database)
    repository.initialize()

    manager = ProspectiveMemoryManager(repository)
    return manager


@pytest.fixture
def builder(manager):
    return ProspectiveMemoryContextBuilder(manager)


def create_record(**overrides):
    now = datetime.now(timezone.utc)

    data = {
        "title": "Review project documentation",
        "description": "Review the project documentation carefully.",
        "action": "Review and update documentation.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "priority": ProspectiveMemoryPriority.NORMAL,
        "status": ProspectiveMemoryStatus.PENDING,
        "source": ProspectiveMemorySource.USER,
        "source_agent": "CoordinatorAgent",
        "created_at": now,
        "updated_at": now,
    }

    data.update(overrides)

    due_at = data.get("due_at")
    expires_at = data.get("expires_at")

    timestamps = [
        value
        for value in (due_at, expires_at)
        if value is not None
    ]

    if timestamps:
        earliest = min(timestamps)

        if earliest < data["created_at"]:
            data["created_at"] = earliest - timedelta(days=1)

    return ProspectiveMemoryRecord(**data)


def remember(manager, **overrides):
    record = create_record(**overrides)

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    return record


def test_build_context_returns_relevant_intentions(builder, manager):
    remember(
        manager,
        title="Review Python project",
        description="Review Python application architecture.",
        action="Inspect Python modules.",
    )

    remember(
        manager,
        title="Prepare vacation",
        description="Book travel accommodation.",
        action="Prepare travel documents.",
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Review Python application",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 1
    assert context.memories[0].title == "Review Python project"


def test_build_context_excludes_irrelevant_intentions(builder, manager):
    remember(
        manager,
        title="Prepare vacation",
        description="Book travel accommodation.",
        action="Prepare travel documents.",
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Analyze Python source code",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_higher_priority_breaks_relevance_tie(builder, manager):
    remember(
        manager,
        title="Review Python project",
        description="Review Python application.",
        action="Inspect Python modules.",
        priority=ProspectiveMemoryPriority.LOW,
    )

    remember(
        manager,
        title="Review Python project",
        description="Review Python application.",
        action="Inspect Python modules.",
        priority=ProspectiveMemoryPriority.CRITICAL,
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Review Python application",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 2
    assert (
        context.memories[0].priority
        == ProspectiveMemoryPriority.CRITICAL
    )


def test_build_context_excludes_expired_intentions(builder, manager):
    now = datetime.now(timezone.utc)

    remember(
        manager,
        title="Review Python project",
        description="Review Python application.",
        action="Inspect Python modules.",
        expires_at=now - timedelta(minutes=1),
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Review Python application",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_build_context_respects_configured_limit(manager):
    for index in range(7):
        remember(
            manager,
            title=f"Review Python project {index}",
            description="Review Python application.",
            action="Inspect Python modules.",
        )

    builder = ProspectiveMemoryContextBuilder(
        manager,
        limit=3,
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Review Python application",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 3


def test_builder_rejects_invalid_limit(manager):
    with pytest.raises(ValueError):
        ProspectiveMemoryContextBuilder(manager, limit=0)

    with pytest.raises(ValueError):
        ProspectiveMemoryContextBuilder(manager, limit=11)


def test_builder_rejects_untrusted_recipient(builder):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=uuid4(),
            objective="Review Python project",
            recipient_agent="UnknownAgent",
        )


def test_builder_rejects_invalid_task_id(builder):
    with pytest.raises(TypeError):
        builder.build_context(
            task_id="invalid",
            objective="Review Python project",
            recipient_agent="PlanningAgent",
        )


def test_builder_rejects_empty_objective(builder):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=uuid4(),
            objective=" ",
            recipient_agent="PlanningAgent",
        )


def test_builder_rejects_empty_recipient(builder):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=uuid4(),
            objective="Review Python project",
            recipient_agent="",
        )


def test_context_preserves_task_and_recipient(builder):
    task_id = uuid4()

    context = builder.build_context(
        task_id=task_id,
        objective="Review Python project",
        recipient_agent="VerificationAgent",
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "VerificationAgent"


def test_builder_excludes_cancelled_intentions(builder, manager):
    record = remember(
        manager,
        title="Review Python project",
        description="Review Python application.",
        action="Inspect Python modules.",
    )

    manager.cancel(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Review Python application",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []