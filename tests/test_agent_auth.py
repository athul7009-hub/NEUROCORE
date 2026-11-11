from datetime import timedelta, timezone, datetime
from uuid import uuid4

import pytest

from app.core.agent_auth import AgentAuthenticator
from app.core.schemas import AgentMessage, MessageType
from concurrent.futures import ThreadPoolExecutor


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
def test_expired_replay_entries_are_cleaned_up():
    auth = create_authenticator()

    expired_id = "expired-message"
    auth._seen_messages[expired_id] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    signed = auth.sign(create_message(), "PlanningAgent")

    assert auth.verify(signed) is True
    assert expired_id not in auth._seen_messages


def test_concurrent_replay_is_rejected():
    auth = create_authenticator()
    signed = auth.sign(create_message(), "PlanningAgent")

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(
            executor.map(lambda _: auth.verify(signed), range(10))
        )

    assert results.count(True) == 1
    assert results.count(False) == 9

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
def test_empty_agent_key_is_rejected():
    try:
        AgentAuthenticator({"PlanningAgent": ""})
        assert False, "Expected missing key rejection."
    except ValueError as exc:
        assert "missing" in str(exc).lower()


def test_invalid_hex_key_is_rejected():
    try:
        AgentAuthenticator({"PlanningAgent": "not-a-valid-hex-key"})
        assert False, "Expected invalid hexadecimal rejection."
    except ValueError as exc:
        assert "hexadecimal" in str(exc).lower()


def test_short_key_is_rejected():
    try:
        AgentAuthenticator({"PlanningAgent": "aabb"})
        assert False, "Expected short key rejection."
    except ValueError as exc:
        assert "32 bytes" in str(exc)


def test_all_registered_agent_keys_are_loaded():
    auth = create_authenticator()

    assert set(auth._keys) == {
        "PlanningAgent",
        "FileAnalysisAgent",
        "VerificationAgent",
    }
@pytest.mark.parametrize("invalid_message", [None, "invalid", {}, 123])
def test_sign_rejects_non_agent_messages(invalid_message):
    auth = create_authenticator()

    with pytest.raises(
        TypeError,
        match="Only AgentMessage instances can be signed",
    ):
        auth.sign(invalid_message, "PlanningAgent")
@pytest.mark.parametrize("invalid_message", [None, "invalid", {}, 123])
def test_verify_rejects_non_agent_messages(invalid_message):
    auth = create_authenticator()

    assert auth.verify(invalid_message) is False
@pytest.mark.parametrize("invalid_age", [0, -1, True, 1.5, "300"])
def test_invalid_max_age_is_rejected(invalid_age):
    with pytest.raises(
        ValueError,
        match="Maximum message age must be a positive integer",
    ):
        AgentAuthenticator(
            {"PlanningAgent": TEST_KEY},
            max_age_seconds=invalid_age,
        )