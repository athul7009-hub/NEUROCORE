
from unittest.mock import patch, call

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

        mock_tool_executor.assert_called_once()

        executor_args = mock_tool_executor.call_args
        assert executor_args.args == (runtime.tool_registry,)

        assert "execution_ledger" in executor_args.kwargs

        ledger = executor_args.kwargs["execution_ledger"]
        assert ledger is not None

        mock_coordinator.assert_called_once_with(
            tool_executor=mock_tool_executor.return_value,
            database=ledger.database,
        )

        mock_chat_service.assert_called_once_with()


def test_runtime_recovers_execution_ledger_before_executor_creation():
    events = []

    with (
        patch("app.runtime.SQLiteDatabase") as mock_database_class,
        patch("app.runtime.ToolExecutionLedger") as mock_ledger_class,
        patch("app.runtime.ToolExecutor") as mock_executor_class,
        patch("app.runtime.create_coordinator") as mock_coordinator,
        patch("app.runtime.ChatService"),
    ):
        database = mock_database_class.return_value
        ledger = mock_ledger_class.return_value

        database.initialize.side_effect = lambda: events.append(
            "database_initialized"
        )
        ledger.recover_after_restart.side_effect = lambda: events.append(
            "recovery_completed"
        )
        mock_executor_class.side_effect = lambda *args, **kwargs: (
            events.append("executor_created") or object()
        )

        runtime = create_runtime()

        assert events == [
            "database_initialized",
            "recovery_completed",
            "executor_created",

        ]

        mock_ledger_class.assert_called_once_with(database)
        mock_executor_class.assert_called_once_with(
            mock_executor_class.call_args.args[0],
            execution_ledger=ledger,
        )

        assert mock_coordinator.call_args.kwargs["tool_executor"] is runtime.tool_executor
        assert mock_coordinator.call_args.kwargs["database"] is database
