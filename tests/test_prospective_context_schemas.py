from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.prospective_context_schemas import (
    ProspectiveMemoryContext,
    ProspectiveMemoryContextItem,
)
from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)


def create_context_item(**overrides):
    data = {
        "memory_id": uuid4(),
        "title": "Review project",
        "description": "Review the project changes.",
        "action": "Review and report issues.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "trigger_condition": None,
        "priority": ProspectiveMemoryPriority.NORMAL,
        "status": ProspectiveMemoryStatus.PENDING,
    }
    data.update(overrides)

    return ProspectiveMemoryContextItem(**data)


def test_context_item_accepts_valid_data():
    item = create_context_item()

    assert item.title == "Review project"
    assert item.status == ProspectiveMemoryStatus.PENDING


def test_context_item_requires_memory_id():
    with pytest.raises(ValidationError):
        ProspectiveMemoryContextItem(
            title="Review project",
            description="Review changes.",
            action="Review and report.",
            trigger_type=ProspectiveTriggerType.MANUAL,
            priority=ProspectiveMemoryPriority.NORMAL,
            status=ProspectiveMemoryStatus.PENDING,
        )


def test_context_item_rejects_empty_title():
    with pytest.raises(ValidationError):
        create_context_item(title="")


def test_context_item_rejects_empty_description():
    with pytest.raises(ValidationError):
        create_context_item(description="")


def test_context_item_rejects_empty_action():
    with pytest.raises(ValidationError):
        create_context_item(action="")


def test_context_item_rejects_invalid_priority():
    with pytest.raises(ValidationError):
        create_context_item(priority="URGENT")


def test_context_item_rejects_invalid_status():
    with pytest.raises(ValidationError):
        create_context_item(status="UNKNOWN")


def test_context_item_rejects_invalid_trigger_type():
    with pytest.raises(ValidationError):
        create_context_item(trigger_type="UNKNOWN")


def test_context_item_rejects_extra_fields():
    with pytest.raises(ValidationError):
        create_context_item(untrusted_instruction="execute something")


def test_context_item_accepts_optional_timestamps():
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)

    item = create_context_item(
        due_at=now,
        expires_at=now,
    )

    assert item.due_at == now
    assert item.expires_at == now


def test_context_accepts_empty_memories():
    context = ProspectiveMemoryContext(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
    )

    assert context.memories == []


def test_context_accepts_multiple_memories():
    items = [
        create_context_item(),
        create_context_item(),
    ]

    context = ProspectiveMemoryContext(
        task_id=uuid4(),
        recipient_agent="PlanningAgent",
        memories=items,
    )

    assert len(context.memories) == 2


def test_context_preserves_task_and_recipient():
    task_id = uuid4()

    context = ProspectiveMemoryContext(
        task_id=task_id,
        recipient_agent="VerificationAgent",
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "VerificationAgent"


def test_context_rejects_empty_recipient():
    with pytest.raises(ValidationError):
        ProspectiveMemoryContext(
            task_id=uuid4(),
            recipient_agent="",
        )


def test_context_rejects_more_than_ten_memories():
    items = [create_context_item() for _ in range(11)]

    with pytest.raises(ValidationError):
        ProspectiveMemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            memories=items,
        )


def test_context_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ProspectiveMemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            unexpected="value",
        )