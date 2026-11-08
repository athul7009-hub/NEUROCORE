
from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)


def create_record(**overrides):
    now = datetime.now(timezone.utc)

    data = {
        "title": "Review project",
        "description": "Review the latest project changes.",
        "action": "Inspect the implementation and test results.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "source": ProspectiveMemorySource.USER,
        "source_agent": "CoordinatorAgent",
        "created_at": now,
        "updated_at": now,
    }
    data.update(overrides)

    return ProspectiveMemoryRecord(**data)


# -------------------------------
# Identifiers and defaults
# -------------------------------

def test_generates_unique_memory_ids():
    first = create_record()
    second = create_record()

    assert isinstance(first.memory_id, UUID)
    assert first.memory_id != second.memory_id


def test_default_values():
    record = create_record()

    assert record.status == ProspectiveMemoryStatus.PENDING
    assert record.priority == ProspectiveMemoryPriority.NORMAL
    assert record.sensitivity is not None
    assert record.due_at is None
    assert record.expires_at is None
    assert record.trigger_condition is None
    assert record.triggered_at is None
    assert record.completed_at is None
    assert record.is_protected is False


# -------------------------------
# Trigger validation
# -------------------------------

def test_accepts_time_trigger():
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now + timedelta(hours=1),
    )

    assert record.trigger_type == ProspectiveTriggerType.TIME


def test_time_trigger_requires_due_at():
    with pytest.raises(ValidationError):
        create_record(
            trigger_type=ProspectiveTriggerType.TIME,
        )


def test_time_trigger_rejects_trigger_condition():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            trigger_type=ProspectiveTriggerType.TIME,
            due_at=now + timedelta(hours=1),
            trigger_condition="When approval arrives.",
        )


@pytest.mark.parametrize(
    "trigger_type",
    [
        ProspectiveTriggerType.EVENT,
        ProspectiveTriggerType.CONDITION,
    ],
)
def test_event_and_condition_triggers_require_condition(trigger_type):
    with pytest.raises(ValidationError):
        create_record(trigger_type=trigger_type)


@pytest.mark.parametrize(
    "trigger_type",
    [
        ProspectiveTriggerType.EVENT,
        ProspectiveTriggerType.CONDITION,
    ],
)
def test_event_and_condition_triggers_accept_condition(trigger_type):
    record = create_record(
        trigger_type=trigger_type,
        trigger_condition="When the file scan finishes.",
    )

    assert record.trigger_condition == "When the file scan finishes."


@pytest.mark.parametrize(
    "trigger_type",
    [
        ProspectiveTriggerType.EVENT,
        ProspectiveTriggerType.CONDITION,
    ],
)
def test_event_and_condition_reject_due_at(trigger_type):
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            trigger_type=trigger_type,
            trigger_condition="When approval arrives.",
            due_at=now + timedelta(hours=1),
        )


def test_manual_trigger_rejects_due_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            due_at=now + timedelta(hours=1),
        )


def test_manual_trigger_rejects_trigger_condition():
    with pytest.raises(ValidationError):
        create_record(
            trigger_condition="When approval arrives.",
        )


# -------------------------------
# Priority validation
# -------------------------------

@pytest.mark.parametrize(
    "priority",
    list(ProspectiveMemoryPriority),
)
def test_accepts_all_priorities(priority):
    record = create_record(priority=priority)

    assert record.priority == priority


# -------------------------------
# Required fields and text
# -------------------------------

@pytest.mark.parametrize(
    "field",
    [
        "title",
        "description",
        "action",
        "trigger_type",
        "source",
        "source_agent",
    ],
)
def test_required_fields(field):
    data = {
        "title": "Review project",
        "description": "Review project changes.",
        "action": "Inspect test results.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "source": ProspectiveMemorySource.USER,
        "source_agent": "CoordinatorAgent",
    }

    del data[field]

    with pytest.raises(ValidationError):
        ProspectiveMemoryRecord(**data)


@pytest.mark.parametrize(
    "field",
    ["title", "description", "action", "source_agent"],
)
def test_rejects_blank_required_text(field):
    with pytest.raises(ValidationError):
        create_record(**{field: "   "})


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "T" * 201),
        ("description", "D" * 1001),
        ("action", "A" * 1001),
        ("trigger_condition", "C" * 1001),
        ("source_agent", "A" * 101),
    ],
)
def test_rejects_strings_exceeding_maximum_length(field, value):
    data = {
        "trigger_type": ProspectiveTriggerType.EVENT,
        "trigger_condition": "Valid condition",
    }
    data[field] = value

    with pytest.raises(ValidationError):
        create_record(**data)


def test_rejects_blank_trigger_condition():
    with pytest.raises(ValidationError):
        create_record(
            trigger_type=ProspectiveTriggerType.EVENT,
            trigger_condition="   ",
        )


# -------------------------------
# Timestamp validation
# -------------------------------

def test_accepts_valid_due_and_expiration_dates():
    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now + timedelta(hours=1),
        expires_at=now + timedelta(days=1),
    )

    assert record.due_at is not None
    assert record.expires_at is not None


@pytest.mark.parametrize(
    "field",
    [
        "created_at",
        "updated_at",
        "due_at",
        "expires_at",
        "triggered_at",
        "completed_at",
    ],
)
def test_rejects_naive_timestamps(field):
    data = {}

    if field == "due_at":
        data["trigger_type"] = ProspectiveTriggerType.TIME

    if field == "triggered_at":
        data.update({
            "status": ProspectiveMemoryStatus.TRIGGERED,
        })

    if field == "completed_at":
        now = datetime.now(timezone.utc)
        data.update({
            "status": ProspectiveMemoryStatus.COMPLETED,
            "triggered_at": now,
        })

    if field == "expires_at":
        data["status"] = ProspectiveMemoryStatus.EXPIRED

    data[field] = datetime.now()

    with pytest.raises(ValidationError):
        create_record(**data)


def test_rejects_updated_at_before_created_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            created_at=now,
            updated_at=now - timedelta(seconds=1),
        )


def test_rejects_due_at_before_created_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            trigger_type=ProspectiveTriggerType.TIME,
            created_at=now,
            due_at=now - timedelta(seconds=1),
        )


def test_rejects_expires_at_equal_to_created_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            created_at=now,
            expires_at=now,
        )


def test_rejects_expires_at_before_due_at():
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            trigger_type=ProspectiveTriggerType.TIME,
            due_at=now + timedelta(hours=2),
            expires_at=now + timedelta(hours=1),
        )


# -------------------------------
# Lifecycle validation
# -------------------------------

def test_accepts_pending_status():
    record = create_record(
        status=ProspectiveMemoryStatus.PENDING,
    )

    assert record.status == ProspectiveMemoryStatus.PENDING


def test_triggered_status_requires_triggered_at():
    with pytest.raises(ValidationError):
        create_record(
            status=ProspectiveMemoryStatus.TRIGGERED,
        )


def test_accepts_triggered_status_with_timestamp():
    triggered_at = datetime.now(timezone.utc)

    record = create_record(
        status=ProspectiveMemoryStatus.TRIGGERED,
        triggered_at=triggered_at,
    )

    assert record.triggered_at == triggered_at


def test_completed_status_requires_triggered_at_and_completed_at():
    with pytest.raises(ValidationError):
        create_record(
            status=ProspectiveMemoryStatus.COMPLETED,
        )


def test_accepts_completed_status_with_valid_timestamps():
    triggered_at = datetime.now(timezone.utc)
    completed_at = triggered_at + timedelta(minutes=5)

    record = create_record(
        status=ProspectiveMemoryStatus.COMPLETED,
        triggered_at=triggered_at,
        completed_at=completed_at,
    )

    assert record.triggered_at == triggered_at
    assert record.completed_at == completed_at


def test_rejects_completed_at_without_triggered_at():
    with pytest.raises(ValidationError):
        create_record(
            completed_at=datetime.now(timezone.utc),
        )


def test_rejects_completed_at_before_triggered_at():
    triggered_at = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        create_record(
            status=ProspectiveMemoryStatus.COMPLETED,
            triggered_at=triggered_at,
            completed_at=triggered_at - timedelta(seconds=1),
        )


@pytest.mark.parametrize(
    "status",
    [
        ProspectiveMemoryStatus.PENDING,
        ProspectiveMemoryStatus.TRIGGERED,
        ProspectiveMemoryStatus.CANCELLED,
        ProspectiveMemoryStatus.EXPIRED,
    ],
)
def test_non_completed_status_rejects_completed_at(status):
    now = datetime.now(timezone.utc)

    data = {
        "status": status,
        "completed_at": now + timedelta(minutes=1),
    }

    if status == ProspectiveMemoryStatus.TRIGGERED:
        data["triggered_at"] = now

    if status == ProspectiveMemoryStatus.EXPIRED:
        data["expires_at"] = now + timedelta(days=1)

    with pytest.raises(ValidationError):
        create_record(**data)


def test_expired_status_requires_expiration_timestamp():
    with pytest.raises(ValidationError):
        create_record(
            status=ProspectiveMemoryStatus.EXPIRED,
        )


def test_accepts_expired_status_with_expiration_timestamp():
    now = datetime.now(timezone.utc)

    record = create_record(
        status=ProspectiveMemoryStatus.EXPIRED,
        expires_at=now + timedelta(days=1),
    )

    assert record.status == ProspectiveMemoryStatus.EXPIRED


# -------------------------------
# Model configuration
# -------------------------------

def test_rejects_unexpected_fields():
    with pytest.raises(ValidationError):
        create_record(unexpected_field="not allowed")


def test_accepts_source_task_id():
    task_id = UUID("12345678-1234-5678-1234-567812345678")

    record = create_record(source_task_id=task_id)

    assert record.source_task_id == task_id


def test_accepts_source_agent():
    record = create_record(source_agent="PlanningAgent")

    assert record.source_agent == "PlanningAgent"
