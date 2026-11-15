
from unittest.mock import patch

from app.runtime import create_runtime


def test_create_runtime_initializes_application_services():
    with (
        patch("app.runtime.create_coordinator") as mock_coordinator,
        patch("app.runtime.ChatService") as mock_chat_service,
        patch("app.runtime.ToolExecutor") as mock_tool_executor,
    ):
        runtime = create_runtime()

        assert runtime.coordinator is mock_coordinator.return_value
        assert runtime.chat_service is mock_chat_service.return_value

        assert runtime.tool_registry.list_tools() == ["scan_directory"]
        assert runtime.tool_executor is mock_tool_executor.return_value

        mock_coordinator.assert_called_once()
        mock_chat_service.assert_called_once()
        mock_tool_executor.assert_called_once_with(runtime.tool_registry)
