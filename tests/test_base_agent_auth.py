
import pytest

from app.agents.base_agent import BaseAgent
from app.core.agent_auth import AgentAuthenticator
from app.core.schemas import AgentMessage, MessageType


class AuthTestAgent(BaseAgent):
    def __init__(self):
        super().__init__("TestAgent", "Authentication test agent")

    def process(self, message: AgentMessage) -> AgentMessage:
        return AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient=message.sender,
            message_type=MessageType.RESULT,
            payload={"result": "success"},
        )


def create_authenticator():
    return AgentAuthenticator({
        "Coordinator": "a" * 64,
        "TestAgent": "b" * 64,
    })


def create_request(authenticator, recipient="TestAgent"):
    message = AgentMessage(
        task_id="12345678-1234-5678-1234-567812345678",
        sender="Coordinator",
        recipient=recipient,
        message_type=MessageType.TASK,
        payload={"objective": "Test authentication"},
    )
    return authenticator.sign(message, "Coordinator")


def test_authenticated_request_returns_signed_response():
    authenticator = create_authenticator()
    agent = AuthTestAgent()
    agent.set_authenticator(authenticator)

    response = agent.process_authenticated(
        create_request(authenticator)
    )

    assert response.sender == "TestAgent"
    assert response.signature is not None
    assert authenticator.verify(response) is True


def test_wrong_recipient_is_rejected():
    authenticator = create_authenticator()
    agent = AuthTestAgent()
    agent.set_authenticator(authenticator)

    request = create_request(authenticator, recipient="OtherAgent")

    with pytest.raises(PermissionError):
        agent.process_authenticated(request)


def test_unauthenticated_request_is_rejected():
    authenticator = create_authenticator()
    agent = AuthTestAgent()
    agent.set_authenticator(authenticator)

    request = AgentMessage(
        task_id="12345678-1234-5678-1234-567812345678",
        sender="Coordinator",
        recipient="TestAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Test authentication"},
    )

    with pytest.raises(PermissionError):
        agent.process_authenticated(request)


def test_replayed_request_is_rejected():
    authenticator = create_authenticator()
    agent = AuthTestAgent()
    agent.set_authenticator(authenticator)

    request = create_request(authenticator)

    agent.process_authenticated(request)

    with pytest.raises(PermissionError):
        agent.process_authenticated(request)
