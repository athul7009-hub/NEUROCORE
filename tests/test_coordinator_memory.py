
from unittest.mock import Mock, patch

import pytest

from app.agents.coordinator import Coordinator
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.registry import AgentRegistry
from app.core.schemas import TaskIntent, TaskRequest, MessageType
from app.core.agent_auth import AgentAuthenticator
from app.memory.database import SQLiteDatabase
from app.memory.manager import MemoryManager
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import MemoryStatus


@pytest.fixture
def memory_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "memory.db")
    repository = EpisodicMemoryRepository(database)
    manager = MemoryManager(repository)
    manager.initialize()
    return manager


def create_authenticator():
    return AgentAuthenticator({
        "FileAnalysisAgent": "a" * 64,
        "PlanningAgent": "b" * 64,
        "VerificationAgent": "c" * 64,
    })


def create_coordinator(registry, memory_manager):
    return Coordinator(
        registry,
        create_authenticator(),
        memory_manager,
    )


def test_successful_file_analysis_is_remembered(memory_manager):
    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())
    coordinator = create_coordinator(registry, memory_manager)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    scan_result = {
        "root": "D:/Projects/Demo",
        "total_files": 10,
        "total_size_bytes": 1000,
        "extension_counts": {".py": 10},
        "duplicates": [],
        "recoverable_bytes": 0,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    with patch(
        "app.agents.file_analysis_agent.run_scan",
        return_value=scan_result,
    ):
        response = coordinator.handle_task(task)

    memory = memory_manager.get_task(task.task_id)

    assert response.message_type == MessageType.RESULT
    assert memory is not None
    assert memory.status == MemoryStatus.COMPLETED
    assert memory.agent_name == "FileAnalysisAgent"
    assert "10 files scanned" in memory.summary
    assert "D:/Projects/Demo" not in memory.summary


def test_successful_planning_task_is_remembered(memory_manager):
    registry = AgentRegistry()
    registry.register(PlanningAgent())
    coordinator = create_coordinator(registry, memory_manager)

    task = TaskRequest(
        user_input="Create a project analysis plan",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    memory = memory_manager.get_task(task.task_id)

    assert response.message_type == MessageType.RESULT
    assert memory is not None
    assert memory.status == MemoryStatus.COMPLETED
    assert memory.agent_name == "PlanningAgent"
    assert "5 steps" in memory.summary
    assert task.user_input not in memory.summary


def test_failed_agent_task_is_remembered(memory_manager):
    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())
    coordinator = create_coordinator(registry, memory_manager)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    with patch(
        "app.agents.file_analysis_agent.run_scan",
        side_effect=PermissionError("Private directory"),
    ):
        response = coordinator.handle_task(task)

    memory = memory_manager.get_task(task.task_id)

    assert response.message_type == MessageType.ERROR
    assert memory is not None
    assert memory.status == MemoryStatus.FAILED
    assert memory.agent_name == "FileAnalysisAgent"
    assert "Private directory" not in memory.summary


def test_invalid_planning_response_is_not_remembered(memory_manager):
    from tests.test_coordinator import MaliciousTestAgent

    registry = AgentRegistry()
    registry.register(MaliciousTestAgent({}))
    coordinator = create_coordinator(registry, memory_manager)

    task = TaskRequest(
        user_input="Create a test plan",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.RESULT
    assert memory_manager.get_task(task.task_id) is None


def test_memory_failure_does_not_change_agent_response():
    registry = AgentRegistry()
    registry.register(PlanningAgent())

    failing_manager = Mock()
    failing_manager.remember_task.side_effect = OSError(
        "Database unavailable"
    )

    coordinator = create_coordinator(registry, failing_manager)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.RESULT
    failing_manager.remember_task.assert_called_once()
