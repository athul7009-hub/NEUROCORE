from unittest.mock import Mock

from app.memory.manager import MemoryManager
from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.working_manager import WorkingMemoryManager
from app.memory.prospective_manager import ProspectiveMemoryManager
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.agents.coordinator import Coordinator
from app.agents.registry import AgentRegistry
from app.core.schemas import AgentMessage
from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
    MemoryIdentityRequest,
)
from app.memory.meta_schemas import MetaMemoryType
from app.core.agent_auth import AgentAuthenticator


COORDINATOR = "CoordinatorAgent"


@pytest.fixture
def authenticator():
    return AgentAuthenticator({
        "Coordinator": "d" * 64,
        "FileAnalysisAgent": "a" * 64,
        "PlanningAgent": "b" * 64,
        "VerificationAgent": "c" * 64,
    })


@pytest.fixture
def managers():
    return {
        "episodic": Mock(spec=MemoryManager),
        "semantic": Mock(spec=SemanticMemoryManager),
        "procedural": Mock(spec=ProceduralMemoryManager),
        "working": Mock(spec=WorkingMemoryManager),
        "prospective": Mock(spec=ProspectiveMemoryManager),
    }


@pytest.fixture
def coordinator(authenticator, managers):
    return Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
        memory_manager=managers["episodic"],
        semantic_memory_manager=managers["semantic"],
        procedural_memory_manager=managers["procedural"],
        working_memory_manager=managers["working"],
        prospective_memory_manager=managers["prospective"],
    )


def make_request(memory_type, *, task_id=None):
    return MemoryIdentityRequest(
        memory_type=memory_type,
        memory_id=uuid4(),
        task_id=task_id,
    )


def test_coordinator_initializes_identity_resolver(coordinator):
    assert coordinator.memory_identity_resolver is not None


def test_coordinator_does_not_initialize_resolver_without_all_managers(
    authenticator,
    managers,
):
    coordinator = Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
        memory_manager=managers["episodic"],
        semantic_memory_manager=managers["semantic"],
        procedural_memory_manager=managers["procedural"],
        working_memory_manager=managers["working"],
        prospective_memory_manager=None,
    )

    assert coordinator.memory_identity_resolver is None


def test_inspect_memory_identity_delegates_to_resolver(
    coordinator,
):
    request = make_request(MetaMemoryType.EPISODIC)

    expected = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=request.memory_id,
        exists=True,
        lifecycle_status="active",
        availability=MemoryIdentityAvailability.AVAILABLE,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        inspect_mock = Mock(return_value=expected)

        monkeypatch.setattr(
            coordinator.memory_identity_resolver,
            "inspect",
            inspect_mock,
        )

        result = coordinator.inspect_memory_identity(request)

    assert result == expected

    inspect_mock.assert_called_once_with(
        request,
        requesting_agent=COORDINATOR,
    )


@pytest.mark.parametrize(
    "memory_type",
    list(MetaMemoryType),
)
def test_coordinator_supports_all_memory_types(
    coordinator,
    memory_type,
):
    task_id = (
        uuid4()
        if memory_type == MetaMemoryType.WORKING
        else None
    )

    request = make_request(
        memory_type,
        task_id=task_id,
    )

    expected = MemoryIdentityAssessment(
        memory_type=memory_type,
        memory_id=request.memory_id,
        task_id=task_id,
        exists=False,
        availability=MemoryIdentityAvailability.NOT_FOUND,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            coordinator.memory_identity_resolver,
            "inspect",
            Mock(return_value=expected),
        )

        result = coordinator.inspect_memory_identity(request)

    assert result == expected
    assert result.memory_type == memory_type


def test_coordinator_rejects_invalid_identity_request(coordinator):
    with pytest.raises(TypeError):
        coordinator.inspect_memory_identity(
            "invalid-request"
        )


def test_coordinator_rejects_inspection_when_managers_missing(
    authenticator,
):
    coordinator = Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
    )

    request = make_request(MetaMemoryType.EPISODIC)

    with pytest.raises(RuntimeError):
        coordinator.inspect_memory_identity(request)


def test_identity_inspection_does_not_change_task_routes(
    coordinator,
):
    original_routes = coordinator.routes.copy()

    request = make_request(MetaMemoryType.EPISODIC)

    expected = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id=request.memory_id,
        exists=False,
        availability=MemoryIdentityAvailability.NOT_FOUND,
    )

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            coordinator.memory_identity_resolver,
            "inspect",
            Mock(return_value=expected),
        )

        coordinator.inspect_memory_identity(request)

    assert coordinator.routes == original_routes
