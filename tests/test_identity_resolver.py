
from uuid import uuid4
from unittest.mock import Mock

import pytest

from app.memory.identity_resolver import MemoryIdentityResolver
from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
    MemoryIdentityRequest,
)
from app.memory.meta_schemas import MetaMemoryType
from app.memory.schemas import MemoryLifecycleStatus
from app.memory.semantic_schemas import SemanticMemoryStatus
from app.memory.procedural_schemas import ProceduralMemoryStatus


COORDINATOR = "CoordinatorAgent"
UNAUTHORIZED_AGENT = "PlanningAgent"


@pytest.fixture
def managers():
    return {
        "episodic": Mock(),
        "semantic": Mock(),
        "procedural": Mock(),
        "working": Mock(),
        "prospective": Mock(),
    }


@pytest.fixture
def resolver(managers):
    return MemoryIdentityResolver(
        episodic_manager=managers["episodic"],
        semantic_manager=managers["semantic"],
        procedural_manager=managers["procedural"],
        working_manager=managers["working"],
        prospective_manager=managers["prospective"],
    )


def make_request(memory_type, *, task_id=None):
    return MemoryIdentityRequest(
        memory_type=memory_type,
        memory_id=uuid4(),
        task_id=task_id,
    )


def test_inspects_active_episodic_memory(resolver, managers):
    request = make_request(MetaMemoryType.EPISODIC)

    managers["episodic"].inspect_identity.return_value = (
        MemoryLifecycleStatus.ACTIVE
    )

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert isinstance(result, MemoryIdentityAssessment)
    assert result.memory_type == MetaMemoryType.EPISODIC
    assert result.memory_id == request.memory_id
    assert result.exists is True
    assert result.availability == MemoryIdentityAvailability.AVAILABLE
    assert result.lifecycle_status == MemoryLifecycleStatus.ACTIVE.value

    managers["episodic"].inspect_identity.assert_called_once_with(
        request.memory_id,
        requesting_agent=COORDINATOR,
    )


def test_inspects_archived_episodic_memory(resolver, managers):
    request = make_request(MetaMemoryType.EPISODIC)

    managers["episodic"].inspect_identity.return_value = (
        MemoryLifecycleStatus.ARCHIVED
    )

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result.exists is True
    assert result.availability == MemoryIdentityAvailability.INACTIVE
    assert result.lifecycle_status == MemoryLifecycleStatus.ARCHIVED.value


def test_returns_not_found_for_missing_episodic_memory(
    resolver,
    managers,
):
    request = make_request(MetaMemoryType.EPISODIC)
    managers["episodic"].inspect_identity.return_value = None

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result.exists is False
    assert result.availability == MemoryIdentityAvailability.NOT_FOUND
    assert result.lifecycle_status is None


@pytest.mark.parametrize(
    ("status", "expected_availability"),
    [
        (
            SemanticMemoryStatus.CANDIDATE,
            MemoryIdentityAvailability.UNAVAILABLE,
        ),
        (
            SemanticMemoryStatus.VALIDATED,
            MemoryIdentityAvailability.AVAILABLE,
        ),
        (
            SemanticMemoryStatus.DEPRECATED,
            MemoryIdentityAvailability.INACTIVE,
        ),
    ],
)
def test_maps_semantic_memory_status(
    resolver,
    managers,
    status,
    expected_availability,
):
    request = make_request(MetaMemoryType.SEMANTIC)
    managers["semantic"].inspect_identity.return_value = status

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result.exists is True
    assert result.lifecycle_status == status.value
    assert result.availability == expected_availability

    managers["semantic"].inspect_identity.assert_called_once_with(
        request.memory_id,
        requesting_agent=COORDINATOR,
    )


@pytest.mark.parametrize(
    ("status", "expected_availability"),
    [
        (
            ProceduralMemoryStatus.CANDIDATE,
            MemoryIdentityAvailability.UNAVAILABLE,
        ),
        (
            ProceduralMemoryStatus.VALIDATED,
            MemoryIdentityAvailability.AVAILABLE,
        ),
        (
            ProceduralMemoryStatus.DEPRECATED,
            MemoryIdentityAvailability.INACTIVE,
        ),
    ],
)
def test_maps_procedural_memory_status(
    resolver,
    managers,
    status,
    expected_availability,
):
    request = make_request(MetaMemoryType.PROCEDURAL)
    managers["procedural"].inspect_identity.return_value = status

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result.exists is True
    assert result.lifecycle_status == status.value
    assert result.availability == expected_availability


def test_preserves_working_memory_assessment(resolver, managers):
    task_id = uuid4()
    request = make_request(MetaMemoryType.WORKING, task_id=task_id)

    assessment = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.WORKING,
        memory_id=request.memory_id,
        task_id=task_id,
        exists=True,
        lifecycle_status="active",
        availability=MemoryIdentityAvailability.AVAILABLE,
    )

    managers["working"].inspect_identity.return_value = assessment

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result == assessment
    assert result.task_id == task_id

    managers["working"].inspect_identity.assert_called_once_with(
        request.memory_id,
        task_id,
        requesting_agent=COORDINATOR,
    )


def test_preserves_prospective_memory_assessment(resolver, managers):
    request = make_request(MetaMemoryType.PROSPECTIVE)

    assessment = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.PROSPECTIVE,
        memory_id=request.memory_id,
        exists=True,
        lifecycle_status="pending",
        availability=MemoryIdentityAvailability.AVAILABLE,
    )

    managers["prospective"].inspect_identity.return_value = assessment

    result = resolver.inspect(request, requesting_agent=COORDINATOR)

    assert result == assessment

    managers["prospective"].inspect_identity.assert_called_once_with(
        request.memory_id,
        requesting_agent=COORDINATOR,
    )


def test_rejects_non_coordinator_before_lookup(resolver, managers):
    request = make_request(MetaMemoryType.EPISODIC)

    with pytest.raises(PermissionError):
        resolver.inspect(request, requesting_agent=UNAUTHORIZED_AGENT)

    for manager in managers.values():
        manager.inspect_identity.assert_not_called()


@pytest.mark.parametrize(
    "memory_type",
    list(MetaMemoryType),
)
def test_rejects_unauthorized_agent_for_every_memory_type(
    resolver,
    managers,
    memory_type,
):
    task_id = (
        uuid4()
        if memory_type == MetaMemoryType.WORKING
        else None
    )
    request = make_request(memory_type, task_id=task_id)

    with pytest.raises(PermissionError):
        resolver.inspect(request, requesting_agent="UnknownAgent")

    for manager in managers.values():
        manager.inspect_identity.assert_not_called()


def test_rejects_invalid_request_type(resolver, managers):
    with pytest.raises(TypeError):
        resolver.inspect(
            "not-a-memory-identity-request",
            requesting_agent=COORDINATOR,
        )

    for manager in managers.values():
        manager.inspect_identity.assert_not_called()
