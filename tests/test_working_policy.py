from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.schemas import MemorySensitivity
from app.memory.working_policy import WorkingMemoryPolicy
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


@pytest.fixture
def policy():
    return WorkingMemoryPolicy()


@pytest.fixture
def record():
    now = datetime.now(timezone.utc)

    return WorkingMemoryRecord(
        task_id=uuid4(),
        key="analysis_result",
        entry_type=WorkingMemoryEntryType.INTERMEDIATE_RESULT,
        content={"result": "success"},
        source_agent="PlanningAgent",
        sensitivity=MemorySensitivity.INTERNAL,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def test_trusted_agent_can_store_own_entry(policy, record):
    assert policy.evaluate_storage(record, "PlanningAgent")


def test_untrusted_agent_cannot_store(policy, record):
    assert not policy.evaluate_storage(record, "UnknownAgent")


def test_agent_cannot_impersonate_another_source(policy, record):
    assert not policy.evaluate_storage(record, "FileAnalysisAgent")


def test_expired_entry_cannot_be_stored(policy, record):
    now = datetime.now(timezone.utc)

    expired_record = record.model_copy(
        update={
            "created_at": now - timedelta(seconds=2),
            "updated_at": now - timedelta(seconds=2),
            "expires_at": now - timedelta(seconds=1),
        }
    )

    assert not policy.evaluate_storage(
        expired_record,
        "PlanningAgent",
    )


def test_disallowed_sensitivity_cannot_be_stored(policy, record):
    restricted_record = record.model_copy(
        update={"sensitivity": MemorySensitivity.RESTRICTED}
    )

    assert not policy.evaluate_storage(
        restricted_record,
        "PlanningAgent",
    )


def test_trusted_agent_can_read_same_task_entry(policy, record):
    assert policy.evaluate_retrieval(
        record,
        "VerificationAgent",
        record.task_id,
    )


def test_untrusted_agent_cannot_read_entry(policy, record):
    assert not policy.evaluate_retrieval(
        record,
        "UnknownAgent",
        record.task_id,
    )


def test_agent_cannot_read_entry_from_another_task(policy, record):
    assert not policy.evaluate_retrieval(
        record,
        "PlanningAgent",
        uuid4(),
    )


def test_expired_entry_cannot_be_retrieved(policy, record):
    now = datetime.now(timezone.utc)

    expired_record = record.model_copy(
        update={
            "created_at": now - timedelta(seconds=2),
            "updated_at": now - timedelta(seconds=2),
            "expires_at": now - timedelta(seconds=1),
        }
    )

    assert not policy.evaluate_retrieval(
        expired_record,
        "PlanningAgent",
        expired_record.task_id,
    )


def test_only_coordinator_can_manage(policy):
    assert policy.can_manage("CoordinatorAgent")
    assert not policy.can_manage("PlanningAgent")


def test_invalid_record_is_rejected_by_storage(policy):
    assert not policy.evaluate_storage(
        object(),
        "PlanningAgent",
    )


def test_invalid_record_is_rejected_by_retrieval(policy):
    assert not policy.evaluate_retrieval(
        object(),
        "PlanningAgent",
        uuid4(),
    )


def test_untrusted_agent_is_not_trusted(policy):
    assert not policy.is_trusted("UnknownAgent")


def test_empty_agent_name_is_not_trusted(policy):
    assert not policy.is_trusted("   ")


def test_invalid_agent_type_is_not_trusted(policy):
    assert not policy.is_trusted(None)