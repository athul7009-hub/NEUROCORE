
import pytest

from app.core.communication_policy import CommunicationPolicy
from app.core.schemas import AgentMessage, MessageType


@pytest.fixture
def policy():
    return CommunicationPolicy()


def create_message(
    recipient="FileAnalysisAgent",
    sender="Coordinator",
    message_type=MessageType.TASK,
    payload=None,
):
    return AgentMessage(
        task_id="12345678-1234-5678-1234-567812345678",
        sender=sender,
        recipient=recipient,
        message_type=message_type,
        payload=payload if payload is not None else {
            "directory": "sample_project"
        },
    )


def test_allows_permitted_file_analysis_payload(policy):
    message = create_message()

    policy.validate_outgoing(message)


def test_allows_permitted_planning_payload(policy):
    message = create_message(
        recipient="PlanningAgent",
        payload={"objective": "Analyze project"},
    )

    policy.validate_outgoing(message)


def test_rejects_unauthorized_payload_field(policy):
    message = create_message(
        payload={
            "directory": "sample_project",
            "password": "secret",
        }
    )

    with pytest.raises(ValueError, match="Unauthorized payload fields"):
        policy.validate_outgoing(message)


def test_rejects_unknown_recipient(policy):
    message = create_message(
        recipient="UnknownAgent",
    )

    with pytest.raises(ValueError, match="No communication policy"):
        policy.validate_outgoing(message)


def test_rejects_non_coordinator_sender(policy):
    message = create_message(sender="PlanningAgent")

    with pytest.raises(ValueError, match="Only the Coordinator"):
        policy.validate_outgoing(message)


def test_rejects_non_task_message(policy):
    message = create_message(
        message_type=MessageType.INFORMATION,
    )

    with pytest.raises(ValueError, match="only permits TASK"):
        policy.validate_outgoing(message)


def test_rejects_empty_payload(policy):
    message = create_message(payload={})

    with pytest.raises(ValueError, match="cannot be empty"):
        policy.validate_outgoing(message)


def test_rejects_oversized_payload():
    policy = CommunicationPolicy(max_payload_bytes=20)

    message = create_message(
        payload={"directory": "a" * 100},
    )

    with pytest.raises(ValueError, match="exceeds"):
        policy.validate_outgoing(message)


def test_rejects_non_json_payload():
    policy = CommunicationPolicy()

    message = create_message(
        payload={"directory": object()},
    )

    with pytest.raises(ValueError, match="valid JSON"):
        policy.validate_outgoing(message)
def test_allows_permitted_verification_payload(policy):
    message = create_message(
        recipient="VerificationAgent",
        payload={
            "planning_result": {
                "sender": "PlanningAgent",
                "message_type": "result",
            }
        },
    )

    policy.validate_outgoing(message)


def test_rejects_unauthorized_verification_payload_field(policy):
    message = create_message(
        recipient="VerificationAgent",
        payload={
            "planning_result": {},
            "password": "secret",
        },
    )

    with pytest.raises(ValueError, match="Unauthorized payload fields"):
        policy.validate_outgoing(message)
@pytest.mark.parametrize(
    "invalid_limit",
    [0, -1, True, 1.5, "1024"],
)
def test_rejects_invalid_payload_limit(invalid_limit):
    with pytest.raises(
        ValueError,
        match="Payload limit must be a positive integer",
    ):
        CommunicationPolicy(max_payload_bytes=invalid_limit)