
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.memory.memory_policy import MemoryPolicy
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)
from app.memory.memory_policy import (
    MemoryPolicy,
    MemorySensitivity,
    MemorySource,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)


@pytest.fixture
def memory_policy():
    return MemoryPolicy()


@pytest.fixture
def memory_record():
    return EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="File analysis completed.",
        created_at=datetime.now(timezone.utc),
    )


def test_allows_public_coordinator_memory(
    memory_policy, memory_record
):
    assert memory_policy.evaluate(
        memory_record,
        MemorySensitivity.PUBLIC,
        MemorySource.COORDINATOR,
    )


def test_allows_internal_system_memory(
    memory_policy, memory_record
):
    assert memory_policy.evaluate(
        memory_record,
        MemorySensitivity.INTERNAL,
        MemorySource.SYSTEM,
    )


@pytest.mark.parametrize(
    "sensitivity",
    [
        MemorySensitivity.CONFIDENTIAL,
        MemorySensitivity.RESTRICTED,
    ],
)
def test_rejects_sensitive_memory(
    memory_policy, memory_record, sensitivity
):
    assert not memory_policy.evaluate(
        memory_record,
        sensitivity,
        MemorySource.COORDINATOR,
    )


def test_rejects_invalid_sensitivity(
    memory_policy, memory_record
):
    assert not memory_policy.evaluate(
        memory_record,
        "internal",
        MemorySource.COORDINATOR,
    )


def test_rejects_invalid_source(
    memory_policy, memory_record
):
    assert not memory_policy.evaluate(
        memory_record,
        MemorySensitivity.INTERNAL,
        "coordinator",
    )


def test_rejects_invalid_record(memory_policy):
    assert not memory_policy.evaluate(
        "not a memory record",
        MemorySensitivity.INTERNAL,
        MemorySource.COORDINATOR,
    )


@pytest.mark.parametrize(
    "agent",
   [
    "CoordinatorAgent",
    "FileAnalysisAgent",
    "PlanningAgent",
    "VerificationAgent",
    ]   
)
def test_allows_trusted_agent_to_retrieve_internal_memory(
    memory_policy, memory_record, agent
):
    assert memory_policy.evaluate_retrieval(
        memory_record,
        requesting_agent=agent,
    )


@pytest.mark.parametrize(
    "sensitivity",
    [
        MemorySensitivity.PUBLIC,
        MemorySensitivity.INTERNAL,
    ],
)
def test_allows_permitted_sensitivity(
    memory_policy, memory_record, sensitivity
):
    record = memory_record.model_copy(
        update={"sensitivity": sensitivity}
    )

    assert memory_policy.evaluate_retrieval(
        record,
        requesting_agent="CoordinatorAgent",
    )


@pytest.mark.parametrize(
    "sensitivity",
    [
        MemorySensitivity.CONFIDENTIAL,
        MemorySensitivity.RESTRICTED,
        MemorySensitivity.LEGACY_UNCLASSIFIED,
    ],
)
def test_denies_restricted_sensitivity(
    memory_policy, memory_record, sensitivity
):
    record = memory_record.model_copy(
        update={"sensitivity": sensitivity}
    )

    assert not memory_policy.evaluate_retrieval(
        record,
        requesting_agent="CoordinatorAgent",
    )


def test_denies_unknown_agent(memory_policy, memory_record):
    assert not memory_policy.evaluate_retrieval(
        memory_record,
        requesting_agent="UnknownAgent",
    )


@pytest.mark.parametrize(
    "agent",
    ["", " ", 123, None],
)
def test_rejects_invalid_requesting_agent(
    memory_policy, memory_record, agent
):
    assert not memory_policy.evaluate_retrieval(
        memory_record,
        requesting_agent=agent,
    )


def test_rejects_invalid_retrieval_record(memory_policy):
    assert not memory_policy.evaluate_retrieval(
        "not a memory record",
        requesting_agent="CoordinatorAgent",
    )
