import pytest

from app.agents.base_agent import BaseAgent
from app.agents.registry import AgentRegistry
from app.core.schemas import AgentMessage, MessageType


class DummyAgent(BaseAgent):
    def process(self, message: AgentMessage) -> AgentMessage:
        return AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient=message.sender,
            message_type=MessageType.RESULT,
            payload={"status": "completed"},
            in_reply_to=message.message_id,
        )


def test_register_agent():
    registry = AgentRegistry()
    agent = DummyAgent("FileAnalysisAgent", "Analyzes files")

    registry.register(agent)

    assert registry.get("FileAnalysisAgent") is agent


def test_duplicate_agent_rejected():
    registry = AgentRegistry()

    registry.register(DummyAgent("Coordinator", "Coordinates tasks"))

    with pytest.raises(ValueError):
        registry.register(DummyAgent("Coordinator", "Another coordinator"))


def test_unknown_agent_rejected():
    registry = AgentRegistry()

    with pytest.raises(ValueError):
        registry.get("UnknownAgent")


def test_list_agents():
    registry = AgentRegistry()

    registry.register(DummyAgent("PlanningAgent", "Creates plans"))
    registry.register(DummyAgent("FileAnalysisAgent", "Analyzes files"))

    assert registry.list_agents() == [
        "FileAnalysisAgent",
        "PlanningAgent",
    ]


def test_agent_process():
    agent = DummyAgent("FileAnalysisAgent", "Analyzes files")

    message = AgentMessage(
        task_id=__import__("uuid").uuid4(),
        sender="Coordinator",
        recipient="FileAnalysisAgent",
        message_type=MessageType.TASK,
        payload={"action": "analyze"},
    )

    response = agent.process(message)

    assert response.sender == "FileAnalysisAgent"
    assert response.recipient == "Coordinator"
    assert response.message_type == MessageType.RESULT
    assert response.in_reply_to == message.message_id