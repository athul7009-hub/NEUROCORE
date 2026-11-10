
from abc import ABC, abstractmethod

from app.core.agent_auth import AgentAuthenticator
from app.core.schemas import AgentMessage


class BaseAgent(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self._authenticator: AgentAuthenticator | None = None

    def set_authenticator(
        self,
        authenticator: AgentAuthenticator,
    ) -> None:
        self._authenticator = authenticator

    def process_authenticated(
        self,
        message: AgentMessage,
    ) -> AgentMessage:
        if self._authenticator is None:
            raise RuntimeError("Agent authenticator has not been configured.")
        if not isinstance(message, AgentMessage):
            raise TypeError("Only AgentMessage instances can be processed.")
        if message.recipient != self.name:
            raise PermissionError("Message recipient does not match this agent.")

        if not self._authenticator.verify(message):
            raise PermissionError("Incoming message authentication failed.")

        response = self.process(message)

        return self._authenticator.sign(
            response,
            expected_sender=self.name,
        )

    @abstractmethod
    def process(self, message: AgentMessage) -> AgentMessage:
        """Process an incoming message."""
        pass
