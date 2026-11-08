
import pytest

from app.memory.meta_policy import MetaMemoryPolicy
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryType,
)


@pytest.fixture
def policy():
    return MetaMemoryPolicy()


@pytest.fixture
def record():
    return MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id="memory-001",
    )


def test_accepts_valid_metadata_for_storage(policy, record):
    assert policy.evaluate_storage(record) is True


def test_rejects_non_meta_memory_record(policy):
    assert policy.evaluate_storage({"memory_id": "memory-001"}) is False


@pytest.mark.parametrize(
    "memory_type",
    list(MetaMemoryType),
)
def test_accepts_all_supported_memory_types(policy, memory_type):
    record = MetaMemoryRecord(
        memory_type=memory_type,
        memory_id="memory-001",
    )

    assert policy.evaluate_storage(record) is True


@pytest.mark.parametrize(
    "requesting_agent",
    [
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    ],
)
def test_all_trusted_agents_can_retrieve(policy, record, requesting_agent):
    assert policy.evaluate_retrieval(record, requesting_agent) is True


@pytest.mark.parametrize(
    "requesting_agent",
    [
        "",
        "UnknownAgent",
        "coordinatoragent",
        None,
        123,
    ],
)
def test_untrusted_agents_cannot_retrieve(policy, record, requesting_agent):
    assert policy.evaluate_retrieval(record, requesting_agent) is False


def test_rejects_invalid_record_during_retrieval(policy):
    assert policy.evaluate_retrieval(
        {"memory_id": "memory-001"},
        "CoordinatorAgent",
    ) is False


def test_only_coordinator_can_manage(policy):
    assert policy.can_manage("CoordinatorAgent") is True
    assert policy.can_manage("PlanningAgent") is False
    assert policy.can_manage("UnknownAgent") is False


def test_all_trusted_agents_can_record_usage(policy):
    for agent in policy.TRUSTED_AGENTS:
        assert policy.can_record_usage(agent) is True


def test_untrusted_agent_cannot_record_usage(policy):
    assert policy.can_record_usage("UnknownAgent") is False
    assert policy.can_record_usage("") is False
    assert policy.can_record_usage(None) is False
