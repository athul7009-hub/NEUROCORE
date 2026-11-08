
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import uuid4

from app.core.schemas import AgentMessage, MessageType, TaskIntent, TaskRequest
from app.agents.coordinator import Coordinator
from app.agents.planning_agent import PlanningAgent
from app.agents.registry import AgentRegistry
from app.agents.verification_agent import VerificationAgent
from app.memory.database import SQLiteDatabase
from app.memory.repositories.working_memory import WorkingMemoryRepository
from app.memory.working_manager import WorkingMemoryManager
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)

from tests.test_coordinator import create_test_authenticator


def create_working_memory_manager(tmp_path):
    database = SQLiteDatabase(tmp_path / "working_memory.db")
    repository = WorkingMemoryRepository(database)
    manager = WorkingMemoryManager(repository)
    manager.initialize()
    return manager


def create_working_record(task_id, key, content):
    now = datetime.now(timezone.utc)

    return WorkingMemoryRecord(
        task_id=task_id,
        key=key,
        entry_type=WorkingMemoryEntryType.OBSERVATION,
        content=content,
        source_agent="FileAnalysisAgent",
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(hours=1),
    )


def create_test_coordinator(tmp_path, manager):
    registry = AgentRegistry()

    planning_agent = PlanningAgent()
    verification_agent = VerificationAgent()

    registry.register(planning_agent)
    registry.register(verification_agent)

    # Use the same authenticator for the Coordinator and all agents.
    authenticator = create_test_authenticator()

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(authenticator)

    coordinator = Coordinator(
        registry,
        authenticator,
        working_memory_manager=manager,
    )

    return coordinator, planning_agent, verification_agent


def test_coordinator_sends_working_context_to_planning_agent(
    tmp_path,
):
    manager = create_working_memory_manager(tmp_path)
    coordinator, planning_agent, verification_agent = (
        create_test_coordinator(tmp_path, manager)
    )

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    record = create_working_record(
        task.task_id,
        "project_observation",
        {"filename": "report.txt"},
    )

    manager.remember(
        record,
        requesting_agent="FileAnalysisAgent",
    )

    with patch.object(
        planning_agent,
        "process",
        wraps=planning_agent.process,
    ) as planning_mock:
        response = coordinator.handle_task(task)

    assert response.message_type.value == "result"

    planning_message = planning_mock.call_args.args[0]
    context = planning_message.working_memory_context

    assert context is not None
    assert context.task_id == task.task_id
    assert context.recipient_agent == "PlanningAgent"
    assert len(context.entries) == 1
    assert context.entries[0].key == "project_observation"


def test_coordinator_sends_working_context_to_verification_agent(
    tmp_path,
):
    manager = create_working_memory_manager(tmp_path)
    coordinator, planning_agent, verification_agent = (
        create_test_coordinator(tmp_path, manager)
    )

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    record = create_working_record(
        task.task_id,
        "current_task_state",
        {"status": "analysis_completed"},
    )

    manager.remember(
        record,
        requesting_agent="FileAnalysisAgent",
    )

    with patch.object(
        verification_agent,
        "process",
        wraps=verification_agent.process,
    ) as verification_mock:
        response = coordinator.handle_task(task)

    assert response.message_type.value == "result"

    verification_message = verification_mock.call_args.args[0]
    context = verification_message.working_memory_context

    assert context is not None
    assert context.task_id == task.task_id
    assert context.recipient_agent == "VerificationAgent"
    assert len(context.entries) == 1
    assert context.entries[0].key == "current_task_state"


def test_coordinator_never_shares_another_tasks_working_memory(
    tmp_path,
):
    manager = create_working_memory_manager(tmp_path)
    coordinator, planning_agent, verification_agent = (
        create_test_coordinator(tmp_path, manager)
    )

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    unrelated_task_id = uuid4()

    current_record = create_working_record(
        task.task_id,
        "current_task_entry",
        {"value": "current"},
    )

    unrelated_record = create_working_record(
        unrelated_task_id,
        "unrelated_task_entry",
        {"value": "unrelated"},
    )

    manager.remember(
        current_record,
        requesting_agent="FileAnalysisAgent",
    )
    manager.remember(
        unrelated_record,
        requesting_agent="FileAnalysisAgent",
    )

    with patch.object(
        planning_agent,
        "process",
        wraps=planning_agent.process,
    ) as planning_mock:
        response = coordinator.handle_task(task)

    assert response.message_type.value == "result"

    context = (
        planning_mock.call_args.args[0].working_memory_context
    )

    assert context.task_id == task.task_id

    keys = [entry.key for entry in context.entries]

    assert "current_task_entry" in keys
    assert "unrelated_task_entry" not in keys


def test_coordinator_rejects_working_memory_authorization_failure(
    tmp_path,
):
    manager = create_working_memory_manager(tmp_path)
    coordinator, planning_agent, verification_agent = (
        create_test_coordinator(tmp_path, manager)
    )

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        manager,
        "search",
        side_effect=PermissionError(
            "Unauthorized working memory access."
        ),
    ):
        with patch.object(
            planning_agent,
            "process",
            wraps=planning_agent.process,
        ) as planning_mock:
            response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type.value == "error"
    assert "unauthorized" in response.payload["error"].lower()

    planning_mock.assert_not_called()


def test_working_memory_content_is_not_promoted_to_episodic_memory(
    tmp_path,
):
    manager = create_working_memory_manager(tmp_path)
    coordinator, _, _ = create_test_coordinator(tmp_path, manager)

    class MemoryCapture:
        def __init__(self):
            self.records = []

        def remember_task(self, record):
            self.records.append(record)

    memory_capture = MemoryCapture()
    coordinator.memory_manager = memory_capture

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    private_content = "TEMPORARY_INTERNAL_OBSERVATION_8472"

    response = AgentMessage(
        task_id=task.task_id,
        sender="PlanningAgent",
        recipient="Coordinator",
        message_type=MessageType.RESULT,
        payload={
            "steps": [
                "Analyze requirements",
                "Create implementation plan",
            ],
            "temporary_data": private_content,
        },
    )

    coordinator._remember_task(
        task,
        "PlanningAgent",
        response,
    )

    assert len(memory_capture.records) == 1

    episodic_record = memory_capture.records[0]

    assert episodic_record.status.value == "completed"
    assert private_content not in episodic_record.summary
    assert "2 steps" in episodic_record.summary
