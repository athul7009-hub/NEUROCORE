
import pytest
from uuid import uuid4

from app.memory.database import SQLiteDatabase
from app.memory.procedural_context_builder import (
    ProceduralMemoryContextBuilder,
)
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
)


@pytest.fixture
def manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "procedural_context.db")
    database.initialize()

    from app.memory.repositories.procedural_memory import (
        ProceduralMemoryRepository,
    )

    repository = ProceduralMemoryRepository(database)
    memory_manager = ProceduralMemoryManager(repository)
    memory_manager.initialize()

    return memory_manager


@pytest.fixture
def builder(manager):
    return ProceduralMemoryContextBuilder(manager)


def create_record(**overrides):
    data = {
        "name": "Python project setup",
        "description": "Create and configure a Python project.",
        "when_to_use": "When starting a new Python application.",
        "steps": [
            {
                "step_number": 1,
                "instruction": "Create the project directory.",
            },
            {
                "step_number": 2,
                "instruction": "Create a virtual environment.",
            },
        ],
        "source": ProceduralMemorySource.DOCUMENT,
    }
    data.update(overrides)
    return ProceduralMemoryRecord(**data)


def save_validated(manager, record):
    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )
    manager.validate(
        record.procedure_id,
        requesting_agent="CoordinatorAgent",
    )


def test_build_empty_context(builder):
    context = builder.build_context(
        task_id=uuid4(),
        objective="Create a Python application",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []
    assert context.recipient_agent == "PlanningAgent"


def test_build_context_returns_relevant_validated_procedure(
    manager,
    builder,
):
    record = create_record()
    save_validated(manager, record)

    context = builder.build_context(
        task_id=uuid4(),
        objective="Set up a new Python project",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 1
    assert context.memories[0].procedure_id == record.procedure_id


def test_build_context_excludes_candidate_procedures(
    manager,
    builder,
):
    record = create_record()

    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    context = builder.build_context(
        task_id=uuid4(),
        objective="Set up a Python project",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_build_context_excludes_unrelated_procedures(
    manager,
    builder,
):
    record = create_record(
        name="Gardening workflow",
        description="Prepare soil and plant seeds.",
        when_to_use="When starting a vegetable garden.",
    )
    save_validated(manager, record)

    context = builder.build_context(
        task_id=uuid4(),
        objective="Build a Python application",
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_build_context_respects_limit(manager):
    builder = ProceduralMemoryContextBuilder(manager, limit=2)

    records = [
        create_record(name=f"Python project setup {index}")
        for index in range(4)
    ]

    for record in records:
        save_validated(manager, record)

    context = builder.build_context(
        task_id=uuid4(),
        objective="Python project setup",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories) == 2


def test_build_context_preserves_procedure_steps(
    manager,
    builder,
):
    record = create_record()
    save_validated(manager, record)

    context = builder.build_context(
        task_id=uuid4(),
        objective="Set up a Python project",
        recipient_agent="PlanningAgent",
    )

    assert len(context.memories[0].steps) == 2
    assert (
        context.memories[0].steps[0].instruction
        == "Create the project directory."
    )


def test_build_context_preserves_task_and_recipient(
    manager,
    builder,
):
    task_id = uuid4()
    record = create_record()
    save_validated(manager, record)

    context = builder.build_context(
        task_id=task_id,
        objective="Set up a Python project",
        recipient_agent="PlanningAgent",
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "PlanningAgent"


@pytest.mark.parametrize(
    "task_id,objective,recipient",
    [
        ("invalid", "Python project setup", "PlanningAgent"),
        (uuid4(), "", "PlanningAgent"),
        (uuid4(), "Python project setup", ""),
    ],
)
def test_build_context_rejects_invalid_inputs(
    builder,
    task_id,
    objective,
    recipient,
):
    with pytest.raises((TypeError, ValueError)):
        builder.build_context(
            task_id=task_id,
            objective=objective,
            recipient_agent=recipient,
        )


@pytest.mark.parametrize("limit", [0, 11, -1, True, 1.5])
def test_builder_rejects_invalid_limit(manager, limit):
    with pytest.raises(ValueError):
        ProceduralMemoryContextBuilder(
            manager,
            limit=limit,
        )
