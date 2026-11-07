
import pytest

from app.memory.procedural_policy import ProceduralMemoryPolicy
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
    ProceduralMemoryStatus,
)
from app.memory.schemas import MemorySensitivity


def create_record(**overrides):
    data = {
        "name": "Python project setup",
        "description": "Steps to set up a Python project.",
        "when_to_use": "When starting a new Python project.",
        "steps": [
            {
                "step_number": 1,
                "instruction": "Create a project directory.",
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


@pytest.fixture
def policy():
    return ProceduralMemoryPolicy()


def test_storage_allows_candidate_public_record(policy):
    record = create_record(sensitivity=MemorySensitivity.PUBLIC)

    assert policy.evaluate_storage(record) is True


def test_storage_allows_candidate_internal_record(policy):
    record = create_record(sensitivity=MemorySensitivity.INTERNAL)

    assert policy.evaluate_storage(record) is True


def test_storage_rejects_restricted_sensitivity(policy):
    record = create_record(sensitivity=MemorySensitivity.RESTRICTED)

    assert policy.evaluate_storage(record) is False


def test_storage_rejects_validated_record(policy):
    record = create_record(
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_storage(record) is False


def test_storage_rejects_invalid_record(policy):
    assert policy.evaluate_storage("invalid") is False


def test_retrieval_allows_validated_public_record(policy):
    record = create_record(
        sensitivity=MemorySensitivity.PUBLIC,
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is True


def test_retrieval_allows_validated_internal_record(policy):
    record = create_record(
        sensitivity=MemorySensitivity.INTERNAL,
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_retrieval(
        record,
        "VerificationAgent",
    ) is True


def test_retrieval_rejects_candidate_record(policy):
    record = create_record()

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_deprecated_record(policy):
    record = create_record(
        status=ProceduralMemoryStatus.DEPRECATED,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_restricted_sensitivity(policy):
    record = create_record(
        sensitivity=MemorySensitivity.RESTRICTED,
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_retrieval(
        record,
        "PlanningAgent",
    ) is False


def test_retrieval_rejects_untrusted_agent(policy):
    record = create_record(
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_retrieval(
        record,
        "UnknownAgent",
    ) is False


@pytest.mark.parametrize(
    "requesting_agent",
    ["", " ", None, 123],
)
def test_retrieval_rejects_invalid_agent(policy, requesting_agent):
    record = create_record(
        status=ProceduralMemoryStatus.VALIDATED,
        validated_by="CoordinatorAgent",
        validated_at=create_record().created_at,
    )

    assert policy.evaluate_retrieval(
        record,
        requesting_agent,
    ) is False


def test_retrieval_rejects_invalid_record(policy):
    assert policy.evaluate_retrieval(
        "invalid",
        "PlanningAgent",
    ) is False


def test_only_coordinator_can_manage(policy):
    assert policy.can_manage("CoordinatorAgent") is True
    assert policy.can_manage("PlanningAgent") is False
    assert policy.can_manage("VerificationAgent") is False


@pytest.mark.parametrize(
    "requesting_agent",
    ["", " ", None, 123],
)
def test_invalid_agent_cannot_manage(policy, requesting_agent):
    assert policy.can_manage(requesting_agent) is False
