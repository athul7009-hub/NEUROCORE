from abc import ABC, abstractmethod

from app.core.schemas import AgentMessage


class BaseAgent(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    @abstractmethod
    def process(self, message: AgentMessage) -> AgentMessage:
        """Process an incoming message and return a response."""
        pass