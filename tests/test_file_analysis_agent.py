from uuid import uuid4
from unittest.mock import patch

from app.agents.file_analysis_agent import FileAnalysisAgent
from app.core.schemas import AgentMessage, MessageType
from datetime import datetime, timezone

from app.memory.context_schemas import (
    MemoryContext,
    MemoryContextItem,
)
from app.memory.schemas import MemoryStatus

def create_message(directory="C:/TestProject"):
    return AgentMessage(
        task_id=uuid4(),
        sender="Coordinator",
        recipient="FileAnalysisAgent",
        message_type=MessageType.TASK,
        payload={"directory": directory},
    )

def create_memory(summary, status=MemoryStatus.COMPLETED):
    return MemoryContextItem(
        source_task_id=uuid4(),
        intent="ANALYZE_FILES",
        status=status,
        agent_name="FileAnalysisAgent",
        summary=summary,
        completed_at=datetime.now(timezone.utc),
    )

def attach_memory(message, memories):
    message.memory_context = MemoryContext(
        task_id=message.task_id,
        recipient_agent="FileAnalysisAgent",
        memories=memories,
    )
    return message
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

@patch("app.agents.file_analysis_agent.run_scan")
def test_file_analysis_handles_empty_memory_context(mock_scan):
    mock_scan.return_value = {
        "root": "C:/TestProject",
        "total_files": 5,
        "total_size_bytes": 2000,
        "extension_counts": {".py": 5},
        "duplicates": [],
        "recoverable_bytes": 0,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    agent = FileAnalysisAgent()
    message = attach_memory(create_message(), [])

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_evaluation"]["selected_memories"] == []


@patch("app.agents.file_analysis_agent.run_scan")
def test_file_analysis_selects_relevant_memory(mock_scan):
    mock_scan.return_value = {
        "root": "C:/TestProject",
        "total_files": 5,
        "total_size_bytes": 2000,
        "extension_counts": {".py": 5},
        "duplicates": [],
        "recoverable_bytes": 0,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    agent = FileAnalysisAgent()
    memory = create_memory(
        "Analyzed files, file metadata, duplicate files and scan warnings."
    )
    message = attach_memory(create_message(), [memory])

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    selected = response.metadata["memory_evaluation"]["selected_memories"]

    assert len(selected) == 1
    assert selected[0]["source_task_id"] == str(memory.source_task_id)


def test_file_analysis_rejects_mismatched_memory_task_id():
    agent = FileAnalysisAgent()
    message = create_message()

    message.memory_context = MemoryContext(
        task_id=uuid4(),
        recipient_agent="FileAnalysisAgent",
        memories=[],
    )

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "task id mismatch" in response.payload["error"].lower()


def test_file_analysis_rejects_mismatched_memory_recipient():
    agent = FileAnalysisAgent()
    message = create_message()

    message.memory_context = MemoryContext(
        task_id=message.task_id,
        recipient_agent="PlanningAgent",
        memories=[],
    )

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "recipient mismatch" in response.payload["error"].lower()