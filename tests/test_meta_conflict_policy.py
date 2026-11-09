import pytest

from app.memory.meta_conflict_policy import MetaMemoryConflictPolicy
from app.memory.meta_conflict_schemas import MetaMemoryConflictRecord
from app.memory.meta_schemas import MetaMemoryType


@pytest.fixture
def policy():
    return MetaMemoryConflictPolicy()


@pytest.fixture
def valid_record():
    return MetaMemoryConflictRecord(
        memory_type_a=MetaMemoryType.SEMANTIC.value,
        memory_id_a="memory-1",
        memory_type_b=MetaMemoryType.PROCEDURAL.value,
        memory_id_b="memory-2",
        conflict_type="factual",
        confidence_score=0.9,
        rationale="The two memories contain contradictory information.",
    )


def test_allows_valid_conflict_storage(policy, valid_record):
    assert policy.evaluate_storage(valid_record)


def test_rejects_invalid_storage_record(policy):
    assert not policy.evaluate_storage(object())


@pytest.mark.parametrize(
    "agent",
    [
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    ],
)
def test_allows_trusted_agents_to_retrieve(policy, valid_record, agent):
    assert policy.evaluate_retrieval(valid_record, agent)


@pytest.mark.parametrize(
    "agent",
    ["UnknownAgent", "", None],
)
def test_rejects_untrusted_agents(policy, valid_record, agent):
    assert not policy.evaluate_retrieval(valid_record, agent)


def test_rejects_invalid_retrieval_record(policy):
    assert not policy.evaluate_retrieval(object(), "CoordinatorAgent")


def test_only_coordinator_can_review(policy):
    assert policy.can_review("CoordinatorAgent")
    assert not policy.can_review("PlanningAgent")
    assert not policy.can_review("FileAnalysisAgent")
    assert not policy.can_review("UnknownAgent")
    assert not policy.can_review(None)