
from uuid import uuid4

from pydantic import ValidationError

from app.core.schemas import (
    TaskRequest,
    AgentMessage,
    ToolRequest,
    ToolResult,
    MessageType,
    ToolStatus,
)


def test_task_request():
    task = TaskRequest(user_input="Analyze my project folder")

    assert task.user_input == "Analyze my project folder"
    assert task.task_id is not None

    print("PASS: TaskRequest")


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

    print("PASS: AgentMessage")

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

    print("PASS: Agent message reply and metadata")
def test_tool_request():
    action = ToolRequest(
        tool_name="file_scanner",
        parameters={"path": "sample_project"},
    )

    assert action.requires_approval is True
    assert action.dry_run is True

    print("PASS: ToolRequest")


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

    print("PASS: ToolResult")


def test_invalid_task():
    try:
        TaskRequest(user_input="")
    except ValidationError:
        print("PASS: Invalid task rejected")
        return

    raise AssertionError("Empty task was incorrectly accepted")


if __name__ == "__main__":
    test_task_request()
    test_agent_message()
    test_tool_request()
    test_tool_result()
    test_invalid_task()
    test_agent_message_reply()
    print("\nAll schema tests passed!")
