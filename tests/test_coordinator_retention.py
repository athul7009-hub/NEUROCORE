from unittest.mock import MagicMock

from app.agents.coordinator import Coordinator


def test_assess_memory_retention_delegates_to_manager():
    memory_manager = MagicMock()
    memory_manager.assess_retention.return_value = []

    coordinator = Coordinator(
        registry=MagicMock(),
        authenticator=MagicMock(),
        memory_manager=memory_manager,
    )

    result = coordinator.assess_memory_retention(limit=50)

    assert result == []

    memory_manager.assess_retention.assert_called_once_with(
        requesting_agent="CoordinatorAgent",
        limit=50,
    )


def test_assess_memory_retention_without_manager():
    coordinator = Coordinator(
        registry=MagicMock(),
        authenticator=MagicMock(),
    )

    assert coordinator.assess_memory_retention() == []


def test_assess_memory_retention_propagates_authorization_failure():
    memory_manager = MagicMock()
    memory_manager.assess_retention.side_effect = PermissionError(
        "Unauthorized"
    )

    coordinator = Coordinator(
        registry=MagicMock(),
        authenticator=MagicMock(),
        memory_manager=memory_manager,
    )

    try:
        coordinator.assess_memory_retention()
        assert False, "Expected PermissionError"
    except PermissionError:
        pass