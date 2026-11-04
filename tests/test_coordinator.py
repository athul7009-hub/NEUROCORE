
import pytest
from unittest.mock import patch
from app.agents.planning_agent import PlanningAgent
from app.agents.coordinator import Coordinator
from app.agents.registry import AgentRegistry
from app.agents.file_analysis_agent import FileAnalysisAgent

from app.core.schemas import (
    TaskRequest,
    TaskIntent,
    MessageType,
)


@patch("app.agents.file_analysis_agent.run_scan")
def test_coordinator_delegates_task(mock_scan):
    mock_scan.return_value = {
        "root": "D:/Projects/Demo",
        "total_files": 5,
        "total_size_bytes": 1000,
        "extension_counts": {".py": 5},
        "duplicates": [],
        "recoverable_bytes": 0,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())

    coordinator = Coordinator(registry)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "FileAnalysisAgent"
    assert response.task_id == task.task_id
    assert response.message_type == MessageType.RESULT
    assert response.payload["total_files"] == 5

    mock_scan.assert_called_once_with("D:/Projects/Demo")


def test_coordinator_rejects_missing_directory():
    coordinator = Coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "directory" in response.payload["error"].lower()


@pytest.mark.parametrize("directory", ["", "   ", None, 123])
def test_coordinator_rejects_invalid_directory(directory):
    coordinator = Coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": directory},
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    assert "directory" in response.payload["error"].lower()


def test_coordinator_rejects_unregistered_agent():
    coordinator = Coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "not registered" in response.payload["error"].lower()


def test_coordinator_rejects_unconfigured_route():
    coordinator = Coordinator(AgentRegistry())
    coordinator.routes.pop(TaskIntent.FILE_ANALYSIS)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "unsupported task intent" in response.payload["error"].lower()
def test_coordinator_routes_planning_task():
    registry = AgentRegistry()
    registry.register(PlanningAgent())

    coordinator = Coordinator(registry)

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "PlanningAgent"
    assert response.recipient == "Coordinator"
    assert response.task_id == task.task_id
    assert response.message_type == MessageType.RESULT

    assert response.payload["objective"] == task.user_input
    assert len(response.payload["steps"]) == 5