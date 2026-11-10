
from datetime import datetime, timezone
from datetime import datetime, timedelta, timezone
from app.memory.prospective_policy import ProspectiveMemoryPolicy
from app.memory.prospective_schemas import (
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)
from app.memory.schemas import MemorySensitivity


def create_record(**overrides):
    data = {
        "title": "Review project",
        "description": "Review project changes.",
        "action": "Review and report issues.",
        "trigger_type": ProspectiveTriggerType.MANUAL,
        "source": ProspectiveMemorySource.USER,
        "source_agent": "CoordinatorAgent",
    }
    data.update(overrides)
    return ProspectiveMemoryRecord(**data)


def test_storage_accepts_pending_internal_memory():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_storage(create_record()) is True


def test_storage_accepts_public_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record(sensitivity=MemorySensitivity.PUBLIC)

    assert policy.evaluate_storage(record) is True


def test_storage_rejects_restricted_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record(
        sensitivity=MemorySensitivity.RESTRICTED,
    )

    assert policy.evaluate_storage(record) is False


def test_storage_rejects_non_record():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_storage("invalid") is False


def test_storage_rejects_non_pending_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=datetime.now(timezone.utc),
        status=ProspectiveMemoryStatus.TRIGGERED,
        triggered_at=datetime.now(timezone.utc),
    )

    assert policy.evaluate_storage(record) is False


def test_storage_rejects_untrusted_source_agent():
    policy = ProspectiveMemoryPolicy()

    record = create_record(source_agent="UnknownAgent")

    assert policy.evaluate_storage(record) is False


def test_storage_accepts_trusted_source_agents():
    policy = ProspectiveMemoryPolicy()

    for agent in policy.TRUSTED_AGENTS:
        record = create_record(source_agent=agent)
        assert policy.evaluate_storage(record) is True


def test_retrieval_accepts_pending_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record()

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is True


def test_retrieval_accepts_triggered_memory():
    policy = ProspectiveMemoryPolicy()

    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now,
        created_at=now,
        status=ProspectiveMemoryStatus.TRIGGERED,
        triggered_at=now,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is True


def test_retrieval_rejects_completed_memory():
    policy = ProspectiveMemoryPolicy()

    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now,
        created_at=now,
        status=ProspectiveMemoryStatus.COMPLETED,
        triggered_at=now,
        completed_at=now,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_cancelled_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record(
        status=ProspectiveMemoryStatus.CANCELLED,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_expired_memory():
    policy = ProspectiveMemoryPolicy()

    now = datetime.now(timezone.utc)

    record = create_record(
        trigger_type=ProspectiveTriggerType.TIME,
        due_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(minutes=1),
        status=ProspectiveMemoryStatus.EXPIRED,
        created_at=now - timedelta(hours=1),
        updated_at=now - timedelta(hours=1),
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_restricted_memory():
    policy = ProspectiveMemoryPolicy()

    record = create_record(
        sensitivity=MemorySensitivity.RESTRICTED,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_untrusted_agent():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_retrieval(
        create_record(),
        "UnknownAgent",
    ) is False


def test_retrieval_rejects_empty_agent():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_retrieval(
        create_record(),
        "",
    ) is False


def test_retrieval_rejects_non_string_agent():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_retrieval(
        create_record(),
        None,
    ) is False


def test_retrieval_rejects_non_record():
    policy = ProspectiveMemoryPolicy()

    assert policy.evaluate_retrieval(
        "invalid",
        "PlanningAgent",
    ) is False


def test_only_coordinator_can_manage():
    policy = ProspectiveMemoryPolicy()

    assert policy.can_manage("CoordinatorAgent") is True
    assert policy.can_manage("PlanningAgent") is False
    assert policy.can_manage("UnknownAgent") is False
