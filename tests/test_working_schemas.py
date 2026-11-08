
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.schemas import MemorySensitivity
from app.memory.working_schemas import (
    WorkingMemoryContext,
    WorkingMemoryContextItem,
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


@pytest.fixture
def valid_record_data():
    now = datetime.now(timezone.utc)

    return {
        "task_id": uuid4(),
        "key": "project_scan",
        "entry_type": WorkingMemoryEntryType.OBSERVATION,
        "content": {"files_found": 12},
        "source_agent": "FileAnalysisAgent",
        "created_at": now,
        "updated_at": now,
        "expires_at": now + timedelta(hours=1),
    }


def test_record_creation_with_valid_data(valid_record_data):
    record = WorkingMemoryRecord(**valid_record_data)

    assert record.task_id == valid_record_data["task_id"]
    assert record.key == "project_scan"
    assert record.content == {"files_found": 12}
    assert record.sensitivity == MemorySensitivity.INTERNAL
    assert record.entry_id is not None


@pytest.mark.parametrize(
    "entry_type",
    list(WorkingMemoryEntryType),
)
def test_all_entry_types_are_supported(
    valid_record_data,
    entry_type,
):
    valid_record_data["entry_type"] = entry_type

    record = WorkingMemoryRecord(**valid_record_data)

    assert record.entry_type == entry_type


def test_record_rejects_empty_key(valid_record_data):
    valid_record_data["key"] = ""

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_rejects_empty_source_agent(valid_record_data):
    valid_record_data["source_agent"] = ""

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_rejects_naive_timestamps(valid_record_data):
    valid_record_data["created_at"] = datetime.now()
    valid_record_data["updated_at"] = valid_record_data["created_at"]

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_rejects_updated_at_before_created_at(
    valid_record_data,
):
    valid_record_data["updated_at"] = (
        valid_record_data["created_at"] - timedelta(seconds=1)
    )

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_rejects_expiration_before_creation(
    valid_record_data,
):
    valid_record_data["expires_at"] = (
        valid_record_data["created_at"]
    )

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_rejects_unexpected_fields(valid_record_data):
    valid_record_data["unexpected"] = "value"

    with pytest.raises(ValidationError):
        WorkingMemoryRecord(**valid_record_data)


def test_record_uses_default_timestamps():
    now = datetime.now(timezone.utc)

    record = WorkingMemoryRecord(
        task_id=uuid4(),
        key="temporary_result",
        entry_type=WorkingMemoryEntryType.INTERMEDIATE_RESULT,
        content={"result": "success"},
        source_agent="PlanningAgent",
        expires_at=now + timedelta(hours=1),
    )

    assert record.created_at.tzinfo is not None
    assert record.updated_at.tzinfo is not None


def test_context_item_creation():
    item = WorkingMemoryContextItem(
        entry_id=uuid4(),
        key="scan_result",
        entry_type=WorkingMemoryEntryType.OBSERVATION,
        content={"count": 5},
        source_agent="FileAnalysisAgent",
    )

    assert item.key == "scan_result"
    assert item.content["count"] == 5


def test_context_creation():
    task_id = uuid4()

    context = WorkingMemoryContext(
        task_id=task_id,
        recipient_agent="PlanningAgent",
        entries=[],
    )

    assert context.task_id == task_id
    assert context.recipient_agent == "PlanningAgent"
    assert context.entries == []


def test_context_rejects_more_than_20_entries():
    entries = [
        WorkingMemoryContextItem(
            entry_id=uuid4(),
            key=f"entry_{index}",
            entry_type=WorkingMemoryEntryType.AGENT_NOTE,
            content={"index": index},
            source_agent="PlanningAgent",
        )
        for index in range(21)
    ]

    with pytest.raises(ValidationError):
        WorkingMemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            entries=entries,
        )


def test_context_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        WorkingMemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            entries=[],
            unexpected="value",
        )
