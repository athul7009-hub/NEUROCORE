

from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.semantic_context_builder import (
    SemanticMemoryContextBuilder,
)
from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "semantic_context.db")
    database.initialize()

    repository = SemanticMemoryRepository(database)
    memory_manager = SemanticMemoryManager(repository)
    memory_manager.initialize()

    return memory_manager


@pytest.fixture
def builder(manager):
    return SemanticMemoryContextBuilder(manager)


def add_validated_memory(manager, **overrides):
    data = {
        "subject": "Python",
        "predicate": "is_a",
        "object": "Programming language",
        "source": SemanticMemorySource.DOCUMENT,
        "confidence": 0.8,
    }
    data.update(overrides)

    record = SemanticMemoryRecord(**data)

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )
    manager.validate(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )

    return manager.get(
        record.memory_id,
        requesting_agent="CoordinatorAgent",
    )


def test_builds_relevant_context(builder, manager):
    record = add_validated_memory(manager)

    context = builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming language",
    )

    assert len(context.memories) == 1
    assert context.memories[0].memory_id == record.memory_id


def test_rejects_unauthorized_recipient(builder):
    with pytest.raises(PermissionError):
        builder.build_context(
            task_id=uuid4(),
            recipient_agent="UnknownAgent",
            objective="Python programming",
        )


@pytest.mark.parametrize("objective", ["", "   ", None, 123])
def test_rejects_invalid_objective(builder, objective):
    with pytest.raises(ValueError):
        builder.build_context(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            objective=objective,
        )


def test_searches_as_coordinator(builder, manager):
    add_validated_memory(manager)

    original_search = manager.search
    calls = []

    def tracked_search(**kwargs):
        calls.append(kwargs)
        return original_search(**kwargs)

    manager.search = tracked_search

    builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming",
    )

    assert calls == [{
        "requesting_agent": "CoordinatorAgent",
        "limit": builder.CANDIDATE_LIMIT,
    }]


def test_ranks_memories_by_relevance(builder, manager):
    less_relevant = add_validated_memory(
        manager,
        subject="Python",
        predicate="supports",
        object="scripting",
        confidence=1.0,
    )

    more_relevant = add_validated_memory(
        manager,
        subject="Python",
        predicate="is_a",
        object="Programming language",
        confidence=0.1,
    )

    context = builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming language",
    )

    assert context.memories[0].memory_id == more_relevant.memory_id
    assert context.memories[1].memory_id == less_relevant.memory_id


def test_excludes_memories_without_token_overlap(builder, manager):
    add_validated_memory(
        manager,
        subject="Database",
        predicate="uses",
        object="SQLite",
    )

    context = builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming",
    )

    assert context.memories == []


def test_returns_only_validated_memories(builder, manager):
    record = SemanticMemoryRecord(
        subject="Python",
        predicate="is_a",
        object="Programming language",
        source=SemanticMemorySource.DOCUMENT,
    )

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    context = builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming language",
    )

    assert context.memories == []


def test_never_exceeds_max_context_items(builder, manager):
    records = [
        add_validated_memory(
            manager,
            subject=f"Python topic {index}",
            predicate="supports",
            object="programming",
        )
        for index in range(builder.MAX_CONTEXT_ITEMS + 3)
    ]

    context = builder.build_context(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        objective="Python programming",
    )

    assert len(context.memories) == builder.MAX_CONTEXT_ITEMS
    assert all(
        item.memory_id in {record.memory_id for record in records}
        for item in context.memories
    )


def test_preserves_context_metadata(builder, manager):
    record = add_validated_memory(manager)
    task_id = uuid4()

    context = builder.build_context(
        task_id=task_id,
        recipient_agent="VerificationAgent",
        objective="Python programming",
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "VerificationAgent"
    assert context.memories[0].source == record.source
    assert context.memories[0].validated_at == record.validated_at
    assert context.memories[0].validated_by == "CoordinatorAgent"
