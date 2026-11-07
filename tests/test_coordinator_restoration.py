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


def test_restore_memory_delegates_to_manager():
    manager = MagicMock()
    manager.restore_task.return_value = True
    task_id = uuid4()

    coordinator = create_coordinator(manager)

    assert coordinator.restore_memory(task_id) is True

    manager.restore_task.assert_called_once_with(
        task_id,
        requesting_agent="CoordinatorAgent",
    )


def test_restore_memory_returns_false_when_not_archived():
    manager = MagicMock()
    manager.restore_task.return_value = False

    coordinator = create_coordinator(manager)

    assert coordinator.restore_memory(uuid4()) is False


def test_restore_memory_without_manager_raises_error():
    coordinator = create_coordinator(None)

    with pytest.raises(RuntimeError):
        coordinator.restore_memory(uuid4())


def test_restore_memory_propagates_authorization_error():
    manager = MagicMock()
    manager.restore_task.side_effect = PermissionError("Unauthorized.")

    coordinator = create_coordinator(manager)

    with pytest.raises(PermissionError):
        coordinator.restore_memory(uuid4())