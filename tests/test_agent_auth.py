
from datetime import timedelta, timezone, datetime
from uuid import uuid4

from app.core.agent_auth import AgentAuthenticator
from app.core.schemas import AgentMessage, MessageType


TEST_KEY = "a" * 64


def create_authenticator():
    return AgentAuthenticator({
        "PlanningAgent": TEST_KEY,
        "FileAnalysisAgent": "b" * 64,
        "VerificationAgent": "c" * 64,
    })


def create_message(**overrides):
    data = {
        "task_id": uuid4(),
        "sender": "PlanningAgent",
        "recipient": "Coordinator",
        "message_type": MessageType.RESULT,
        "payload": {"objective": "Analyze project"},
    }
    data.update(overrides)
    return AgentMessage(**data)


def test_valid_signature_is_accepted():
    auth = create_authenticator()
    message = create_message()

    signed = auth.sign(message, "PlanningAgent")

    assert auth.verify(signed) is True


def test_modified_payload_is_rejected():
    auth = create_authenticator()
    signed = auth.sign(
        create_message(),
        "PlanningAgent",
    )

    modified = signed.model_copy(
        update={"payload": {"objective": "Malicious change"}}
    )

    assert auth.verify(modified) is False


def test_unknown_agent_is_rejected():
    auth = create_authenticator()
    message = create_message(sender="UnknownAgent")

    assert auth.verify(message) is False


def test_missing_signature_is_rejected():
    auth = create_authenticator()
    message = create_message()

    assert auth.verify(message) is False


def test_expired_message_is_rejected():
    auth = create_authenticator()
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)

    message = create_message(created_at=old_time)
    signed = auth.sign(message, "PlanningAgent")

    assert auth.verify(signed) is False


def test_replayed_message_is_rejected():
    auth = create_authenticator()
    signed = auth.sign(
        create_message(),
        "PlanningAgent",
    )

    assert auth.verify(signed) is True
    assert auth.verify(signed) is False


def test_wrong_signing_identity_is_rejected():
    auth = create_authenticator()
    message = create_message()

    try:
        auth.sign(message, "FileAnalysisAgent")
        assert False, "Expected identity mismatch."
    except ValueError:
        pass
