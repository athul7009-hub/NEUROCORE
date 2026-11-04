
from uuid import uuid4

from pydantic import ValidationError

from app.core.schemas import (
    TaskRequest,
    TaskIntent,
    AgentMessage,
    ToolRequest,
    ToolResult,
    MessageType,
    ToolStatus,
)


def test_task_request():
    task = TaskRequest(
        user_input="Analyze my project folder",
        intent=TaskIntent.FILE_ANALYSIS,
    )

    assert task.user_input == "Analyze my project folder"
    assert task.task_id is not None
    assert task.intent == TaskIntent.FILE_ANALYSIS
    assert task.parameters == {}


def test_invalid_task():
    try:
        TaskRequest(
            user_input="",
            intent=TaskIntent.FILE_ANALYSIS,
        )
    except ValidationError:
        return

    raise AssertionError("Empty task was incorrectly accepted")


def test_agent_message():
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="FileAnalysisAgent",
        recipient="Coordinator",
        message_type=MessageType.RESULT,
        payload={"files_found": 15},
    )

    assert message.task_id == task_id
    assert message.payload["files_found"] == 15
    assert message.priority == 5
    assert message.in_reply_to is None
    assert message.metadata == {}


def test_agent_message_reply():
    task_id = uuid4()
    original_message_id = uuid4()

    reply = AgentMessage(
        task_id=task_id,
        sender="PlanningAgent",
        recipient="Coordinator",
        message_type=MessageType.RESULT,
        payload={"plan": "Analyze project dependencies"},
        in_reply_to=original_message_id,
        metadata={"channel": "internal"},
    )

    assert reply.in_reply_to == original_message_id
    assert reply.metadata["channel"] == "internal"


def test_tool_request():
    action = ToolRequest(
        tool_name="file_scanner",
        parameters={"path": "sample_project"},
    )

    assert action.requires_approval is True
    assert action.dry_run is True


def test_tool_result():
    action_id = uuid4()

    result = ToolResult(
        action_id=action_id,
        status=ToolStatus.EXECUTED,
        success=True,
        message="Operation completed",
    )

    assert result.action_id == action_id
    assert result.success is True
