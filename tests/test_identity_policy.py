
import pytest

from app.memory.identity_policy import MemoryIdentityPolicy
from app.memory.meta_schemas import MetaMemoryType


def test_coordinator_can_inspect_all_memory_types():
    for memory_type in MetaMemoryType:
        MemoryIdentityPolicy.authorize_inspection(
            "CoordinatorAgent",
            memory_type,
        )


@pytest.mark.parametrize(
    "requesting_agent",
    [
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
        "UnknownAgent",
        "",
    ],
)
def test_non_coordinator_cannot_inspect_identity(requesting_agent):
    with pytest.raises(PermissionError):
        MemoryIdentityPolicy.authorize_inspection(
            requesting_agent,
            MetaMemoryType.EPISODIC,
        )


def test_unauthorized_agent_is_rejected_before_memory_type_check():
    with pytest.raises(PermissionError):
        MemoryIdentityPolicy.authorize_inspection(
            "PlanningAgent",
            "invalid",
        )


def test_all_five_memory_types_are_allowed():
    assert MemoryIdentityPolicy.ALLOWED_MEMORY_TYPES == frozenset(
        MetaMemoryType
    )
