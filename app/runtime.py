
from dataclasses import dataclass

from app.agents.coordinator import Coordinator
from app.bootstrap import create_coordinator
from app.llm.chat_service import ChatService
from app.tools.scan_tool import SCAN_DIRECTORY_TOOL
from app.tools.tool_executor import ToolExecutor
from app.tools.tool_registry import ToolRegistry
from app.memory.database import SQLiteDatabase
from app.tools.tool_execution_ledger import ToolExecutionLedger

@dataclass
class NeurocoreRuntime:
    """Provides access to NEUROCORE application services."""

    coordinator: Coordinator
    chat_service: ChatService
    tool_registry: ToolRegistry
    tool_executor: ToolExecutor


def create_runtime() -> NeurocoreRuntime:
    """Initializes the application services."""

    database = SQLiteDatabase()
    database.initialize()

    tool_registry = ToolRegistry()
    tool_registry.register(SCAN_DIRECTORY_TOOL)

    execution_ledger = ToolExecutionLedger(database)
    execution_ledger.recover_after_restart()

    tool_executor = ToolExecutor(
        tool_registry,
        execution_ledger=execution_ledger,
    )

    coordinator = create_coordinator(
        tool_executor=tool_executor,
        database=database,
    )

    chat_service = ChatService()

    return NeurocoreRuntime(
        coordinator=coordinator,
        chat_service=chat_service,
        tool_registry=tool_registry,
        tool_executor=tool_executor,
    )