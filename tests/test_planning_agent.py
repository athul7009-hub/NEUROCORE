
from datetime import datetime, timezone
from uuid import uuid4
from app.llm.reasoning import ReasoningError
from app.agents.planning_agent import PlanningAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan
from app.llm.schemas import ReasoningResponse
from app.memory.context_schemas import MemoryContext, MemoryContextItem
from app.memory.schemas import MemoryStatus


class MockReasoningService:
    def __init__(self, proposed_steps=None):
        self.proposed_steps = proposed_steps or [
            "Inspect the project structure.",
            "Identify the main components.",
            "Analyze dependencies.",
            "Determine required improvements.",
            "Prepare the implementation plan.",
        ]
        self.last_request = None

    def generate(self, request):
        self.last_request = request

        return ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="A structured plan for the requested task.",
            proposed_steps=self.proposed_steps,
            confidence=0.9,
            limitations=[],
        )


def create_agent():
    reasoning_service = MockReasoningService()
    return PlanningAgent(reasoning_service=reasoning_service)


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


def create_message(task_id=None, **kwargs):
    message_data = {
        "task_id": task_id or uuid4(),
        "sender": "Coordinator",
        "recipient": "PlanningAgent",
        "message_type": MessageType.TASK,
        "payload": {"objective": "Analyze my project"},
    }
    message_data.update(kwargs)

    return AgentMessage(**message_data)

def test_planning_agent_creates_plan():
    agent = create_agent()
    message = create_message()

    response = agent.process(message)

    assert response.sender == "PlanningAgent"
    assert response.recipient == "Coordinator"
    assert response.task_id == message.task_id
    assert response.message_type == MessageType.RESULT
    assert response.in_reply_to == message.message_id

    plan = TaskPlan.model_validate(response.payload)

    assert plan.objective == "Analyze my project"
    assert len(plan.steps) == 5
    assert plan.requires_approval is True
    assert response.metadata["reasoning"]["model_generated"] is True


def test_planning_agent_rejects_missing_objective():
    agent = create_agent()

    message = create_message(payload={})
    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert "objective" in response.payload["error"].lower()


def test_planning_agent_uses_successful_memories():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.COMPLETED,
            "Analyze project structure and dependencies",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_influence"]["selected_count"] == 1
    assert response.metadata["memory_influence"]["completed_count"] == 1
    assert response.metadata["memory_influence"]["failed_count"] == 0


def test_planning_agent_learns_from_failed_memories():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.FAILED,
            "Analyze project structure and dependencies",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_influence"]["selected_count"] == 1
    assert response.metadata["memory_influence"]["failed_count"] == 1


def test_planning_agent_ignores_irrelevant_memories():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.COMPLETED,
            "Prepare restaurant menu and ingredients",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_influence"]["selected_count"] == 0


def test_planning_agent_handles_empty_memory_context():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=MemoryContext(
            task_id=task_id,
            recipient_agent="PlanningAgent",
            memories=[],
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_influence"]["selected_count"] == 0


def test_rejects_memory_context_for_another_agent():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=MemoryContext(
            task_id=task_id,
            recipient_agent="FileAnalysisAgent",
            memories=[],
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert response.payload["error"] == "Memory context recipient mismatch."


def test_rejects_memory_context_from_another_task():
    agent = create_agent()

    message = create_message(
        memory_context=MemoryContext(
            task_id=uuid4(),
            recipient_agent="PlanningAgent",
            memories=[],
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.ERROR
    assert response.payload["error"] == "Memory context task ID mismatch."


def test_unselected_memory_does_not_influence_plan():
    agent = create_agent()
    task_id = uuid4()

    message = create_message(
        task_id=task_id,
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.FAILED,
            "Configure an unrelated database backup process.",
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert response.metadata["memory_influence"]["selected_count"] == 0
def test_selected_memories_are_passed_to_reasoning_service():
    reasoning_service = MockReasoningService()
    agent = PlanningAgent(reasoning_service=reasoning_service)

    task_id = uuid4()
    summary = "Analyze project structure and dependencies"

    message = create_message(
        task_id=task_id,
        memory_context=create_memory_context(
            task_id,
            MemoryStatus.COMPLETED,
            summary,
        ),
    )

    response = agent.process(message)

    assert response.message_type == MessageType.RESULT
    assert reasoning_service.last_request is not None
    assert "episodic" in reasoning_service.last_request.context
    assert summary in reasoning_service.last_request.context

def test_planning_agent_recovers_after_reasoning_failure():
    reasoning_service = MockReasoningService()
    agent = PlanningAgent(reasoning_service=reasoning_service)

    original_generate = reasoning_service.generate
    call_count = 0

    def fail_once(request):
        nonlocal call_count
        call_count += 1

        if call_count == 1:
            raise ReasoningError("Temporary reasoning failure.")

        return original_generate(request)

    reasoning_service.generate = fail_once

    first_response = agent.process(create_message())

    assert first_response.message_type == MessageType.ERROR
    assert "Local reasoning failed" in first_response.payload["error"]

    second_response = agent.process(create_message())

    assert second_response.message_type == MessageType.RESULT
    assert second_response.sender == "PlanningAgent"
    assert len(TaskPlan.model_validate(second_response.payload).steps) == 5
    assert call_count == 2
