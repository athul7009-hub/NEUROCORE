from datetime import datetime, timedelta, timezone

from app.memory.context_schemas import (
    MemoryContext,
    MemoryContextItem,
)
from app.memory.schemas import MemoryStatus
from uuid import uuid4

from app.agents.planning_agent import PlanningAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan

def create_memory_context(task_id, status, summary):
    memory = MemoryContextItem(
        source_task_id=uuid4(),
        intent="plan_task",
        status=status,
        agent_name="PlanningAgent",
        summary=summary,
        completed_at=datetime.now(timezone.utc),
    )

    return MemoryContext(
        task_id=task_id,
        recipient_agent="PlanningAgent",
        memories=[memory],
    )


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

def test_planning_agent_uses_successful_memories():
    agent = PlanningAgent()
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Analyze my project"},
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.COMPLETED,
            "Analyze project structure and dependencies",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert len(response.payload["steps"]) == 6
    assert any(
        "previously completed tasks" in step
        for step in response.payload["steps"]
    )
    assert response.metadata["memory_influence"]["completed_count"] == 1


def test_planning_agent_learns_from_failed_memories():
    agent = PlanningAgent()
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Analyze my project"},
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.FAILED,
            "Analyze project structure and dependency problems",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert len(response.payload["steps"]) == 6
    assert any(
        "preventive checks" in step
        for step in response.payload["steps"]
    )
    assert response.metadata["memory_influence"]["failed_count"] == 1


def test_planning_agent_ignores_irrelevant_memories():
    agent = PlanningAgent()
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Analyze my project"},
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.COMPLETED,
            "Prepare restaurant menu and ingredients",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert len(response.payload["steps"]) == 5
    assert response.metadata["memory_influence"]["selected_count"] == 0


def test_planning_agent_handles_empty_memory_context():
    agent = PlanningAgent()
    task_id = uuid4()

    message = AgentMessage(
        task_id=task_id,
        sender="Coordinator",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Analyze my project"},
        memory_context=MemoryContext(
            task_id=task_id,
            recipient_agent="PlanningAgent",
            memories=[],
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert len(response.payload["steps"]) == 5
    assert response.metadata["memory_influence"]["selected_count"] == 0

def test_rejects_memory_context_for_another_agent():
    task_id = uuid4()

    memory_context = MemoryContext(
        task_id=task_id,
        recipient_agent="FileAnalysisAgent",
        memories=[],
    )

    message = AgentMessage(
        task_id=task_id,
        sender="CoordinatorAgent",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Create a project analysis plan"},
        memory_context=memory_context,
    )

    response = PlanningAgent().process(message)

    assert response.message_type == MessageType.ERROR
    assert response.payload["error"] == (
        "Memory context recipient mismatch."
    )

def test_rejects_memory_context_from_another_task():
    message = AgentMessage(
        task_id=uuid4(),
        sender="CoordinatorAgent",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Create a project analysis plan"},
        memory_context=MemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            memories=[],
        ),
    )

    response = PlanningAgent().process(message)

    assert response.message_type == MessageType.ERROR
    assert response.payload["error"] == (
        "Memory context task ID mismatch."
    )

def test_unselected_memory_does_not_influence_plan():
    task_id = uuid4()

    memory = MemoryContextItem(
        source_task_id=uuid4(),
        intent="plan_task",
        status=MemoryStatus.FAILED,
        agent_name="PlanningAgent",
        summary="Configure an unrelated database backup process.",
        completed_at=datetime.now(timezone.utc),
    )

    message = AgentMessage(
        task_id=task_id,
        sender="CoordinatorAgent",
        recipient="PlanningAgent",
        message_type=MessageType.TASK,
        payload={"objective": "Create a project analysis plan"},
        memory_context=MemoryContext(
            task_id=task_id,
            recipient_agent="PlanningAgent",
            memories=[memory],
        ),
    )

    response = PlanningAgent().process(message)

    assert response.message_type == MessageType.RESULT
    assert len(response.payload["steps"]) == 5

    influence = response.metadata["memory_influence"]

    assert influence["selected_count"] == 0
    assert influence["failed_count"] == 0
