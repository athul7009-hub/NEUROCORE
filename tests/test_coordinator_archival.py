from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.agents.coordinator import Coordinator


def create_coordinator(memory_manager):
    return Coordinator(
        registry=MagicMock(),
        authenticator=MagicMock(),
        memory_manager=memory_manager,
    )


def test_archive_memory_delegates_to_manager():
    memory_manager = MagicMock()
    memory_manager.archive_task.return_value = True
    task_id = uuid4()

    coordinator = create_coordinator(memory_manager)

    result = coordinator.archive_memory(task_id)

    assert result is True

    memory_manager.archive_task.assert_called_once_with(
        task_id,
        requesting_agent="CoordinatorAgent",
    )


def test_archive_memory_returns_false_when_not_archived():
    memory_manager = MagicMock()
    memory_manager.archive_task.return_value = False

    coordinator = create_coordinator(memory_manager)

    assert coordinator.archive_memory(uuid4()) is False


def test_archive_memory_without_manager_raises_error():
    coordinator = create_coordinator(None)

    with pytest.raises(RuntimeError):
        coordinator.archive_memory(uuid4())


def test_archive_memory_propagates_ineligible_memory_error():
    memory_manager = MagicMock()
    memory_manager.archive_task.side_effect = ValueError(
        "Memory is not eligible for archival."
    )

    coordinator = create_coordinator(memory_manager)

    with pytest.raises(ValueError):
        coordinator.archive_memory(uuid4())


def test_archive_memory_propagates_authorization_error():
    memory_manager = MagicMock()
    memory_manager.archive_task.side_effect = PermissionError(
        "Unauthorized."
    )

    coordinator = create_coordinator(memory_manager)

    with pytest.raises(PermissionError):
        coordinator.archive_memory(uuid4())