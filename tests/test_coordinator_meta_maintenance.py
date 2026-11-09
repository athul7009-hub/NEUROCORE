from datetime import datetime, timezone
from unittest.mock import Mock

import pytest

from app.agents.coordinator import Coordinator
from app.agents.registry import AgentRegistry
from app.core.agent_auth import AgentAuthenticator
from app.memory.meta_manager import MetaMemoryManager
from app.memory.meta_maintenance_schemas import (
    MetaMemoryMaintenanceReport,
)


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
def meta_manager():
    return Mock(spec=MetaMemoryManager)


@pytest.fixture
def coordinator(authenticator, meta_manager):
    return Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
        meta_memory_manager=meta_manager,
    )


@pytest.fixture
def maintenance_report():
    now = datetime.now(timezone.utc)

    return MetaMemoryMaintenanceReport(
        total_examined=3,
        assessed=2,
        skipped=1,
        failed=0,
        failed_meta_ids=[],
        started_at=now,
        completed_at=now,
    )


def test_coordinator_initializes_maintenance_manager(coordinator):
    assert coordinator.meta_memory_maintenance_manager is not None


def test_coordinator_does_not_initialize_maintenance_manager(
    authenticator,
):
    coordinator = Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
    )

    assert coordinator.meta_memory_maintenance_manager is None


def test_maintain_meta_memory_delegates_to_manager(
    coordinator,
    maintenance_report,
):
    maintain_mock = Mock(return_value=maintenance_report)

    coordinator.meta_memory_maintenance_manager.maintain = maintain_mock

    result = coordinator.maintain_meta_memory()

    assert result == maintenance_report

    maintain_mock.assert_called_once_with(
        requesting_agent=COORDINATOR,
        batch_size=20,
        now=None,
    )


def test_maintain_meta_memory_passes_custom_parameters(
    coordinator,
    maintenance_report,
):
    maintain_mock = Mock(return_value=maintenance_report)

    coordinator.meta_memory_maintenance_manager.maintain = maintain_mock

    now = datetime.now(timezone.utc)

    result = coordinator.maintain_meta_memory(
        batch_size=10,
        now=now,
    )

    assert result == maintenance_report

    maintain_mock.assert_called_once_with(
        requesting_agent=COORDINATOR,
        batch_size=10,
        now=now,
    )


def test_maintain_meta_memory_rejects_missing_manager(
    authenticator,
):
    coordinator = Coordinator(
        registry=AgentRegistry(),
        authenticator=authenticator,
    )

    with pytest.raises(
        RuntimeError,
        match="Meta-memory manager is not initialized",
    ):
        coordinator.maintain_meta_memory()


def test_maintain_meta_memory_propagates_manager_failure(
    coordinator,
):
    maintain_mock = Mock(
        side_effect=RuntimeError("Maintenance failed.")
    )

    coordinator.meta_memory_maintenance_manager.maintain = maintain_mock

    with pytest.raises(
        RuntimeError,
        match="Maintenance failed",
    ):
        coordinator.maintain_meta_memory()