
from uuid import uuid4

from app.agents.verification_agent import VerificationAgent
from app.core.schemas import AgentMessage, MessageType


def create_plan_message(task_id=None):
    task_id = task_id or uuid4()

    return AgentMessage(
        task_id=task_id,
        sender="PlanningAgent",
        recipient="Coordinator",
        message_type=MessageType.RESULT,
        payload={
            "task_id": str(task_id),
            "objective": "Analyze project",
            "steps": ["Scan files", "Summarize results"],
            "requires_approval": True,
        },
    )


def test_verification_agent_accepts_valid_plan():
    agent = VerificationAgent()
    message = create_plan_message()

    response = agent.process(message)

    assert response.sender == "VerificationAgent"
    assert response.message_type == MessageType.RESULT
    assert response.in_reply_to == message.message_id
    assert response.payload["valid"] is True
    assert response.payload["errors"] == []


def test_verification_agent_rejects_invalid_plan():
    agent = VerificationAgent()

    message = create_plan_message()
    message.payload["steps"] = []

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any(
        "invalid task plan" in error.lower()
        for error in response.payload["errors"]
    )


def test_verification_agent_rejects_error_response():
    agent = VerificationAgent()

    message = create_plan_message()
    message.message_type = MessageType.ERROR
    message.payload = {"error": "Planning failed"}

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any(
        "returned an error" in error.lower()
        for error in response.payload["errors"]
    )


def test_verification_agent_rejects_mismatched_task_id():
    agent = VerificationAgent()
    message = create_plan_message()

    message.payload["task_id"] = str(uuid4())

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any(
        "task id mismatch" in error.lower()
        for error in response.payload["errors"]
    )


def test_verification_agent_rejects_unexpected_sender():
    agent = VerificationAgent()
    message = create_plan_message()
    message.sender = "UnknownAgent"

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any(
        "unexpected source agent" in error.lower()
        for error in response.payload["errors"]
    )


def test_verification_agent_rejects_non_result_message():
    agent = VerificationAgent()
    message = create_plan_message()
    message.message_type = MessageType.INFORMATION

    response = agent.process(message)

    assert response.payload["valid"] is False
    assert any(
        "not a result" in error.lower()
        for error in response.payload["errors"]
    )
