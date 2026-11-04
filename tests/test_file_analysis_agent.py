from uuid import uuid4
from unittest.mock import patch

from app.agents.file_analysis_agent import FileAnalysisAgent
from app.core.schemas import AgentMessage, MessageType


def create_message(directory="C:/TestProject"):
    return AgentMessage(
        task_id=uuid4(),
        sender="Coordinator",
        recipient="FileAnalysisAgent",
        message_type=MessageType.TASK,
        payload={"directory": directory},
    )


@patch("app.agents.file_analysis_agent.run_scan")
def test_successful_scan(mock_scan):
    mock_scan.return_value = {
        "root": "C:/TestProject",
        "total_files": 10,
        "total_size_bytes": 5000,
        "extension_counts": {".py": 5, ".txt": 5},
        "duplicates": [["a.txt", "b.txt"]],
        "recoverable_bytes": 1000,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    agent = FileAnalysisAgent()
    message = create_message()

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.sender == "FileAnalysisAgent"
    assert response.recipient == "Coordinator"
    assert response.task_id == message.task_id
    assert response.in_reply_to == message.message_id
    assert response.payload["total_files"] == 10
    assert response.payload["duplicate_groups"] == 1

    mock_scan.assert_called_once_with("C:/TestProject")


def test_invalid_directory():
    agent = FileAnalysisAgent()
    message = create_message(directory="")

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "error" in response.payload


@patch("app.agents.file_analysis_agent.run_scan")
def test_unapproved_directory(mock_scan):
    mock_scan.side_effect = PermissionError(
        "This directory has not been approved."
    )

    agent = FileAnalysisAgent()
    message = create_message()

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "not been approved" in response.payload["error"]


def test_missing_directory():
    agent = FileAnalysisAgent()
    message = create_message()
    message.payload = {}

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "valid directory" in response.payload["error"]