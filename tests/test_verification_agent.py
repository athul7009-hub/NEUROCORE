
from datetime import datetime, timezone
from uuid import uuid4

from app.agents.verification_agent import VerificationAgent
from app.core.schemas import AgentMessage, MessageType
from app.memory.context_schemas import MemoryContext, MemoryContextItem
from app.memory.schemas import MemoryStatus


def create_plan_message(task_id=None, payload=None, message_type=MessageType.RESULT):
    task_id = task_id or uuid4()

    return AgentMessage(
        task_id=task_id,
        sender="PlanningAgent",
        recipient="Coordinator",
        message_type=message_type,
        in_reply_to=uuid4(),
        signature="runtime-authenticated",
        payload=payload or {
            "task_id": str(task_id),
            "objective": "Analyze project",
            "steps": ["Scan files", "Summarize results"],
            "requires_approval": True,
        },
    )


def create_verification_request(planning_result=None, task_id=None):
    planning_result = planning_result or create_plan_message(task_id)
    return AgentMessage(
        task_id=planning_result.task_id,
        sender="Coordinator",
        recipient="VerificationAgent",
        message_type=MessageType.TASK,
        payload={
            "planning_result": planning_result.model_dump(mode="json")
        },
    )


def create_memory(summary, status=MemoryStatus.COMPLETED):
    return MemoryContextItem(
        source_task_id=uuid4(),
        intent="VERIFY_PLAN",
        status=status,
        agent_name="VerificationAgent",
        summary=summary,
        completed_at=datetime.now(timezone.utc),
    )


def attach_memory(message, memories):
    message.memory_context = MemoryContext(
        task_id=message.task_id,
        recipient_agent="VerificationAgent",
        memories=memories,
    )
    return message


def test_verification_agent_accepts_valid_plan():
    agent = VerificationAgent()
    message = create_verification_request()

    response = agent.process(message)

    assert response.sender == "VerificationAgent"
    assert response.recipient == "Coordinator"
    assert response.message_type == MessageType.RESULT
    assert response.in_reply_to == message.message_id
    assert response.payload["valid"] is True
    assert response.payload["errors"] == []


def test_verification_agent_rejects_invalid_plan():
    agent = VerificationAgent()
    planning_result = create_plan_message(
        payload={
            "task_id": str(uuid4()),
            "objective": "Analyze project",
            "steps": [],
            "requires_approval": True,
        }
    )
    planning_result.payload["task_id"] = str(planning_result.task_id)
    message = create_verification_request(planning_result)

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("invalid task plan" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_error_response():
    agent = VerificationAgent()
    planning_result = create_plan_message(
        message_type=MessageType.ERROR,
        payload={"error": "Planning failed"},
    )
    message = create_verification_request(planning_result)

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("returned an error" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_mismatched_task_id():
    agent = VerificationAgent()
    planning_result = create_plan_message()
    planning_result.payload["task_id"] = str(uuid4())
    message = create_verification_request(planning_result)

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("task id mismatch" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_unexpected_sender():
    agent = VerificationAgent()
    message = create_verification_request()
    message.sender = "UnknownAgent"

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("unexpected request sender" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_non_task_message():
    agent = VerificationAgent()
    message = create_verification_request()
    message.message_type = MessageType.INFORMATION

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("not a task" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_wrong_recipient():
    agent = VerificationAgent()
    message = create_verification_request()
    message.recipient = "PlanningAgent"

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("unexpected request recipient" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_missing_planning_result():
    agent = VerificationAgent()
    message = create_verification_request()
    message.payload = {}

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("missing or invalid planning result" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_unexpected_embedded_sender():
    agent = VerificationAgent()
    planning_result = create_plan_message()
    planning_result.sender = "UnknownAgent"
    message = create_verification_request(planning_result)

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("unexpected source agent" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_missing_signature():
    agent = VerificationAgent()
    planning_result = create_plan_message()
    planning_result.signature = None
    message = create_verification_request(planning_result)

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("authentication is missing" in error.lower() for error in response.payload["errors"])


def test_verification_agent_handles_empty_memory_context():
    agent = VerificationAgent()
    message = attach_memory(create_verification_request(), [])

    response = agent.process(message)

    assert response.payload["valid"] is True
    assert response.metadata["memory_evaluation"]["selected_memories"] == []


def test_verification_agent_selects_relevant_memory():
    agent = VerificationAgent()
    memory = create_memory(
        "Verified agent outputs, validated task plans, "
        "checked structured data and detected inconsistencies."
    )
    message = attach_memory(create_verification_request(), [memory])

    response = agent.process(message)

    assert response.payload["valid"] is True
    selected = response.metadata["memory_evaluation"]["selected_memories"]

    assert len(selected) == 1
    assert selected[0]["source_task_id"] == str(memory.source_task_id)


def test_verification_agent_rejects_mismatched_memory_task_id():
    agent = VerificationAgent()
    message = create_verification_request()

    message.memory_context = MemoryContext(
        task_id=uuid4(),
        recipient_agent="VerificationAgent",
        memories=[],
    )

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("memory context task id mismatch" in error.lower() for error in response.payload["errors"])


def test_verification_agent_rejects_mismatched_memory_recipient():
    agent = VerificationAgent()
    message = create_verification_request()

    message.memory_context = MemoryContext(
        task_id=message.task_id,
        recipient_agent="PlanningAgent",
        memories=[],
    )

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any("memory context recipient mismatch" in error.lower() for error in response.payload["errors"])
