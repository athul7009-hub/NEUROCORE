
import pytest
from unittest.mock import patch
from uuid import uuid4

from app.agents.base_agent import BaseAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.coordinator import Coordinator
from app.agents.registry import AgentRegistry
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.core.agent_auth import AgentAuthenticator

from app.core.schemas import (
    AgentMessage,
    TaskRequest,
    TaskIntent,
    MessageType,
)


def create_test_authenticator():
    return AgentAuthenticator({
        "FileAnalysisAgent": "a" * 64,
        "PlanningAgent": "b" * 64,
        "VerificationAgent": "c" * 64,
    })


def create_coordinator(registry):
    return Coordinator(registry, create_test_authenticator())


class MaliciousTestAgent(BaseAgent):
    def __init__(self, overrides):
        super().__init__(
            name="PlanningAgent",
            description="Agent used for security testing.",
        )
        self.overrides = overrides

    def process(self, message):
        response = AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload={"objective": "Test task"},
            in_reply_to=message.message_id,
        )

        return response.model_copy(update=self.overrides)


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

    coordinator = create_coordinator(registry)

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
    assert response.signature is not None

    mock_scan.assert_called_once_with("D:/Projects/Demo")


def test_coordinator_rejects_missing_directory():
    coordinator = create_coordinator(AgentRegistry())

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
    coordinator = create_coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": directory},
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    assert "directory" in response.payload["error"].lower()


def test_coordinator_rejects_unregistered_agent():
    coordinator = create_coordinator(AgentRegistry())

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
    coordinator = create_coordinator(AgentRegistry())
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

    coordinator = create_coordinator(registry)

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
    assert response.signature is not None


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        (
            {"sender": "FileAnalysisAgent"},
            "identity mismatch",
        ),
        (
            {"task_id": uuid4()},
            "task id mismatch",
        ),
        (
            {"recipient": "User"},
            "recipient",
        ),
        (
            {"in_reply_to": uuid4()},
            "correlation mismatch",
        ),
        (
            {"message_type": MessageType.TASK},
            "response type",
        ),
    ],
)
def test_coordinator_rejects_malicious_agent_responses(
    overrides,
    expected_error,
):
    registry = AgentRegistry()
    registry.register(MaliciousTestAgent(overrides))

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a test plan",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert expected_error in response.payload["error"].lower()
    assert response.signature is None
