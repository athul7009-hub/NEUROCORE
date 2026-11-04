
from uuid import uuid4

from app.agents.planning_agent import PlanningAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan


def test_planning_agent_creates_plan():
    agent = PlanningAgent()
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Analyze my project"},
    )

    response = agent.process(message)

    assert response.sender == "PlanningAgent"
    assert response.recipient == "Coordinator"
    assert response.task_id == task_id
    assert response.message_type == MessageType.RESULT
    assert response.in_reply_to == message.message_id

    plan = TaskPlan.model_validate(response.payload)

    assert plan.objective == "Analyze my project"
    assert len(plan.steps) == 5
    assert plan.requires_approval is True


def test_planning_agent_rejects_missing_objective():
    agent = PlanningAgent()

    message = AgentMessage(
        task_id=uuid4(),
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
    )

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "objective" in response.payload["error"].lower()
