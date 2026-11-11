
import json
import sqlite3
import warnings
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.agents.base_agent import BaseAgent
from app.agents.coordinator import Coordinator
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.registry import AgentRegistry
from app.agents.verification_agent import VerificationAgent
from app.core.agent_auth import AgentAuthenticator
from app.core.communication_audit import CommunicationAudit
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskIntent,
    TaskRequest,
)
from app.llm.schemas import ReasoningResponse


class MockReasoningService:
    def generate(self, request):
        return ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Mock planning response.",
            proposed_steps=[
                "Inspect the project structure.",
                "Identify the main components.",
                "Analyze dependencies.",
                "Determine required improvements.",
                "Prepare the implementation plan.",
            ],
            confidence=0.9,
        )


def create_planning_agent():
    return PlanningAgent(
        reasoning_service=MockReasoningService()
    )


def create_test_authenticator():
    return AgentAuthenticator({
        "Coordinator": "d" * 64,
        "FileAnalysisAgent": "a" * 64,
        "PlanningAgent": "b" * 64,
        "VerificationAgent": "c" * 64,
    })


def create_coordinator(registry):
    if "VerificationAgent" not in registry.list_agents():
        registry.register(VerificationAgent())

    authenticator = create_test_authenticator()

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(authenticator)

    return Coordinator(registry, authenticator)


class MaliciousTestAgent(BaseAgent):
    def __init__(self, overrides):
        super().__init__(
            name="PlanningAgent",
            description="Agent used for security testing.",
        )
        self.overrides = overrides

    def process(self, message):
        response = AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload={"objective": "Test task"},
            in_reply_to=message.message_id,
        )

        return response.model_copy(update=self.overrides)


@patch("app.agents.file_analysis_agent.run_scan")
def test_coordinator_delegates_task(mock_scan):
    mock_scan.return_value = {
        "root": "D:/Projects/Demo",
        "total_files": 5,
        "total_size_bytes": 1000,
        "extension_counts": {".py": 5},
        "duplicates": [],
        "recoverable_bytes": 0,
        "scan_warnings": [],
        "hash_skipped": [],
        "files": [],
    }

    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "FileAnalysisAgent"
    assert response.task_id == task.task_id
    assert response.message_type == MessageType.RESULT
    assert response.payload["total_files"] == 5
    assert response.signature is not None

    mock_scan.assert_called_once_with("D:/Projects/Demo")


def test_coordinator_rejects_missing_directory():
    coordinator = create_coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "directory" in response.payload["error"].lower()


@pytest.mark.parametrize("directory", ["", "   ", None, 123])
def test_coordinator_rejects_invalid_directory(directory):
    coordinator = create_coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": directory},
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    assert "directory" in response.payload["error"].lower()


def test_coordinator_rejects_unregistered_agent():
    coordinator = create_coordinator(AgentRegistry())

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "not registered" in response.payload["error"].lower()


def test_coordinator_rejects_unconfigured_route():
    coordinator = create_coordinator(AgentRegistry())
    coordinator.routes.pop(TaskIntent.FILE_ANALYSIS)

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "unsupported task intent" in response.payload["error"].lower()


def test_coordinator_routes_planning_task():
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "PlanningAgent"
    assert response.recipient == "Coordinator"
    assert response.task_id == task.task_id
    assert response.message_type == MessageType.RESULT
    assert response.payload["objective"] == task.user_input
    assert 1 <= len(response.payload["steps"]) <= 20
    assert response.signature is not None


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"sender": "FileAnalysisAgent"}, "does not match the sender"),
        ({"task_id": uuid4()}, "task id mismatch"),
        ({"recipient": "User"}, "recipient"),
        ({"in_reply_to": uuid4()}, "correlation mismatch"),
        ({"message_type": MessageType.TASK}, "response type"),
    ],
)
def test_coordinator_rejects_malicious_agent_responses(
    overrides,
    expected_error,
):
    registry = AgentRegistry()
    registry.register(MaliciousTestAgent(overrides))

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a test plan",
        intent=TaskIntent.PLAN_TASK,
    )

    response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert expected_error in response.payload["error"].lower()
    assert response.signature is None


def test_coordinator_audits_accepted_communication(tmp_path):
    audit_path = tmp_path / "communication_audit.jsonl"

    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())

    coordinator = create_coordinator(registry)
    coordinator.communication_audit = CommunicationAudit(audit_path)

    with patch("app.agents.file_analysis_agent.run_scan") as mock_scan:
        mock_scan.return_value = {
            "root": "D:/Projects/Demo",
            "total_files": 0,
            "total_size_bytes": 0,
            "extension_counts": {},
            "duplicates": [],
            "recoverable_bytes": 0,
            "scan_warnings": [],
            "hash_skipped": [],
            "files": [],
        }

        task = TaskRequest(
            user_input="Analyze my project",
            intent=TaskIntent.FILE_ANALYSIS,
            parameters={"directory": "D:/Projects/Demo"},
        )

        response = coordinator.handle_task(task)

    assert response.message_type == MessageType.RESULT
    assert audit_path.exists()

    records = audit_path.read_text(encoding="utf-8").splitlines()

    assert len(records) == 1

    record = json.loads(records[0])

    assert record["outcome"] == "accepted"
    assert record["sender"] == "Coordinator"
    assert record["recipient"] == "FileAnalysisAgent"
    assert record["shared_fields"] == ["directory"]


def test_coordinator_audits_rejected_communication(tmp_path):
    audit_path = tmp_path / "communication_audit.jsonl"

    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())

    coordinator = create_coordinator(registry)
    coordinator.communication_audit = CommunicationAudit(audit_path)

    coordinator.communication_policy.allowed_fields[
        "FileAnalysisAgent"
    ] = {"unauthorized_field"}

    task = TaskRequest(
        user_input="Analyze my project",
        intent=TaskIntent.FILE_ANALYSIS,
        parameters={"directory": "D:/Projects/Demo"},
    )

    response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    assert audit_path.exists()

    records = audit_path.read_text(encoding="utf-8").splitlines()

    assert len(records) == 1

    record = json.loads(records[0])

    assert record["outcome"] == "rejected"
    assert record["recipient"] == "FileAnalysisAgent"
    assert "Unauthorized payload fields" in record["reason"]


def test_coordinator_audit_does_not_store_payload_values(tmp_path):
    audit_path = tmp_path / "communication_audit.jsonl"

    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())

    coordinator = create_coordinator(registry)
    coordinator.communication_audit = CommunicationAudit(audit_path)

    private_directory = "D:/Private/NEUROCORE_SECRET_FOLDER"

    with patch("app.agents.file_analysis_agent.run_scan") as mock_scan:
        mock_scan.return_value = {
            "root": private_directory,
            "total_files": 0,
            "total_size_bytes": 0,
            "extension_counts": {},
            "duplicates": [],
            "recoverable_bytes": 0,
            "scan_warnings": [],
            "hash_skipped": [],
            "files": [],
        }

        task = TaskRequest(
            user_input="Analyze my project",
            intent=TaskIntent.FILE_ANALYSIS,
            parameters={"directory": private_directory},
        )

        response = coordinator.handle_task(task)

    assert response.message_type == MessageType.RESULT

    audit_content = audit_path.read_text(encoding="utf-8")

    assert private_directory not in audit_content
    assert "directory" in audit_content
    assert "accepted" in audit_content


def test_coordinator_rejects_memory_authorization_failure(tmp_path):
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)

    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )

    database = SQLiteDatabase(tmp_path / "memory.db")
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        coordinator.memory_context_builder,
        "build_context",
        side_effect=PermissionError("Unauthorized memory retrieval."),
    ):
        with patch.object(
            agent,
            "process",
            wraps=agent.process,
        ) as process_mock:
            response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "unauthorized" in response.payload["error"].lower()

    process_mock.assert_not_called()


@pytest.mark.parametrize(
    "builder_name",
    [
        "semantic_context_builder",
        "procedural_context_builder",
        "working_context_builder",
        "prospective_context_builder",
    ],
)
def test_coordinator_rejects_additional_memory_authorization_failures(
    tmp_path,
    builder_name,
):
    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )
    from app.memory.repositories.semantic_memory import (
        SemanticMemoryRepository,
    )
    from app.memory.repositories.procedural_memory import (
        ProceduralMemoryRepository,
    )
    from app.memory.repositories.working_memory import (
        WorkingMemoryRepository,
    )
    from app.memory.repositories.prospective_memory import (
        ProspectiveMemoryRepository,
    )
    from app.memory.semantic_manager import SemanticMemoryManager
    from app.memory.procedural_manager import ProceduralMemoryManager
    from app.memory.working_manager import WorkingMemoryManager
    from app.memory.prospective_manager import ProspectiveMemoryManager

    database = SQLiteDatabase(tmp_path / "memory.db")

    memory_manager = MemoryManager(
        EpisodicMemoryRepository(database)
    )
    semantic_manager = SemanticMemoryManager(
        SemanticMemoryRepository(database)
    )
    procedural_manager = ProceduralMemoryManager(
        ProceduralMemoryRepository(database)
    )
    working_manager = WorkingMemoryManager(
        WorkingMemoryRepository(database)
    )
    prospective_manager = ProspectiveMemoryManager(
        ProspectiveMemoryRepository(database)
    )

    memory_manager.initialize()
    semantic_manager.initialize()
    procedural_manager.initialize()
    working_manager.initialize()
    prospective_manager.initialize()

    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
        semantic_memory_manager=semantic_manager,
        procedural_memory_manager=procedural_manager,
        working_memory_manager=working_manager,
        prospective_memory_manager=prospective_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    builder = getattr(coordinator, builder_name)

    with patch.object(
        builder,
        "build_context",
        side_effect=PermissionError("Unauthorized memory retrieval."),
    ):
        with patch.object(
            agent,
            "process",
            wraps=agent.process,
        ) as process_mock:
            response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert "unauthorized" in response.payload["error"].lower()

    process_mock.assert_not_called()


@pytest.mark.parametrize(
    "builder_name",
    [
        "semantic_context_builder",
        "procedural_context_builder",
        "working_context_builder",
        "prospective_context_builder",
    ],
)
def test_coordinator_continues_after_additional_memory_database_failure(
    tmp_path,
    builder_name,
):
    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )
    from app.memory.repositories.semantic_memory import (
        SemanticMemoryRepository,
    )
    from app.memory.repositories.procedural_memory import (
        ProceduralMemoryRepository,
    )
    from app.memory.repositories.working_memory import (
        WorkingMemoryRepository,
    )
    from app.memory.repositories.prospective_memory import (
        ProspectiveMemoryRepository,
    )
    from app.memory.semantic_manager import SemanticMemoryManager
    from app.memory.procedural_manager import ProceduralMemoryManager
    from app.memory.working_manager import WorkingMemoryManager
    from app.memory.prospective_manager import ProspectiveMemoryManager

    database = SQLiteDatabase(tmp_path / "memory.db")

    memory_manager = MemoryManager(
        EpisodicMemoryRepository(database)
    )
    semantic_manager = SemanticMemoryManager(
        SemanticMemoryRepository(database)
    )
    procedural_manager = ProceduralMemoryManager(
        ProceduralMemoryRepository(database)
    )
    working_manager = WorkingMemoryManager(
        WorkingMemoryRepository(database)
    )
    prospective_manager = ProspectiveMemoryManager(
        ProspectiveMemoryRepository(database)
    )

    memory_manager.initialize()
    semantic_manager.initialize()
    procedural_manager.initialize()
    working_manager.initialize()
    prospective_manager.initialize()

    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)
    registry.register(VerificationAgent())

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
        semantic_memory_manager=semantic_manager,
        procedural_memory_manager=procedural_manager,
        working_memory_manager=working_manager,
        prospective_memory_manager=prospective_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    builder = getattr(coordinator, builder_name)

    with patch.object(
        builder,
        "build_context",
        side_effect=sqlite3.OperationalError("Database unavailable."),
    ):
        with patch.object(
            agent,
            "process",
            wraps=agent.process,
        ) as process_mock:
            response = coordinator.handle_task(task)

    assert response.sender == "PlanningAgent"
    assert response.message_type == MessageType.RESULT

    process_mock.assert_called_once()
    assert process_mock.call_args.args[0].memory_context is not None


def test_coordinator_continues_when_memory_database_is_unavailable(tmp_path):
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)
    registry.register(VerificationAgent())

    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )

    database = SQLiteDatabase(tmp_path / "memory.db")
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        coordinator.memory_context_builder,
        "build_context",
        side_effect=sqlite3.OperationalError("Database unavailable."),
    ):
        with patch.object(
            agent,
            "process",
            wraps=agent.process,
        ) as process_mock:
            response = coordinator.handle_task(task)

    assert response.sender == "PlanningAgent"
    assert response.message_type == MessageType.RESULT

    process_mock.assert_called_once()
    assert process_mock.call_args.args[0].memory_context is None


def test_coordinator_returns_success_when_memory_persistence_fails(tmp_path):
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)
    registry.register(VerificationAgent())

    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )

    database = SQLiteDatabase(tmp_path / "memory.db")
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    task = TaskRequest(
        user_input="Create a plan to analyze my project",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        memory_manager,
        "remember_task",
        side_effect=sqlite3.OperationalError("Database unavailable."),
    ) as remember_mock:
        response = coordinator.handle_task(task)

    assert response.sender == "PlanningAgent"
    assert response.message_type == MessageType.RESULT
    assert response.signature is not None
    assert len(response.payload["steps"]) == 5

    remember_mock.assert_called_once()


def test_coordinator_handles_unexpected_planning_agent_exception():
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        agent,
        "process",
        side_effect=RuntimeError("Internal processing failure"),
    ):
        response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert response.signature is None
    assert "internal" in response.payload["error"].lower()


def test_coordinator_handles_unexpected_verification_agent_exception():
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    verification_agent = VerificationAgent()
    registry.register(verification_agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    with patch.object(
        verification_agent,
        "process",
        side_effect=RuntimeError("Internal verification failure"),
    ):
        response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert response.signature is None

    error_message = response.payload["error"].lower()

    assert "unexpected internal error" in error_message
    assert "internal verification failure" not in error_message


def test_coordinator_rejects_unauthenticated_verification_response():
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    verification_agent = VerificationAgent()
    registry.register(verification_agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    def return_unauthenticated_response(message):
        return AgentMessage(
            task_id=message.task_id,
            sender="VerificationAgent",
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload={
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": str(message.task_id),
                "errors": [],
            },
            in_reply_to=message.message_id,
        )

    with patch.object(
        verification_agent,
        "process_authenticated",
        side_effect=return_unauthenticated_response,
    ):
        response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert response.signature is None
    assert "authentication failed" in response.payload["error"].lower()


@pytest.mark.parametrize(
    ("payload", "message_type", "expected_error"),
    [
        (
            "invalid report",
            MessageType.RESULT,
            "invalid verification report",
        ),
        (
            {
                "valid": "yes",
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": [],
            },
            MessageType.RESULT,
            "invalid status",
        ),
        (
            {
                "valid": False,
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": [],
            },
            MessageType.RESULT,
            "failed verification",
        ),
        (
            {
                "valid": True,
                "source_agent": "FileAnalysisAgent",
                "task_id": "wrong-task-id",
                "errors": [],
            },
            MessageType.RESULT,
            "source mismatch",
        ),
        (
            {
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": [],
            },
            MessageType.RESULT,
            "task id mismatch",
        ),
        (
            {
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": ["Invalid plan"],
            },
            MessageType.RESULT,
            "contains errors",
        ),
        (
            {
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": "none",
            },
            MessageType.RESULT,
            "contains errors",
        ),
        (
            {
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": "wrong-task-id",
                "errors": [],
            },
            MessageType.ERROR,
            "valid result",
        ),
    ],
)
def test_coordinator_rejects_invalid_verification_reports(
    payload,
    message_type,
    expected_error,
):
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    verification_agent = VerificationAgent()
    registry.register(verification_agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    def return_invalid_response(message):
        response = AgentMessage(
            task_id=message.task_id,
            sender="VerificationAgent",
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload={
                "valid": True,
                "source_agent": "PlanningAgent",
                "task_id": str(message.task_id),
                "errors": [],
            },
            in_reply_to=message.message_id,
        )

        test_payload = (
            dict(payload) if isinstance(payload, dict) else payload
        )

        if (
            isinstance(test_payload, dict)
            and expected_error != "task id mismatch"
        ):
            test_payload["task_id"] = str(message.task_id)

        return AgentMessage.model_construct(
            **{
                **response.model_dump(),
                "payload": test_payload,
                "message_type": message_type,
            }
        )

    def return_authenticated_invalid_response(message):
        invalid_response = return_invalid_response(message)

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)

            return coordinator.authenticator.sign(
                invalid_response,
                expected_sender="VerificationAgent",
            )

    with patch.object(
        verification_agent,
        "process_authenticated",
        side_effect=return_authenticated_invalid_response,
    ):
        response = coordinator.handle_task(task)

    assert response.sender == "Coordinator"
    assert response.message_type == MessageType.ERROR
    assert response.signature is None
    assert expected_error in response.payload["error"].lower()


def test_coordinator_does_not_execute_agent_when_accepted_audit_fails():
    registry = AgentRegistry()
    agent = FileAnalysisAgent()
    registry.register(agent)

    coordinator = create_coordinator(registry)

    with patch.object(
        coordinator.communication_audit,
        "record",
        side_effect=OSError("Audit storage unavailable"),
    ):
        with patch(
            "app.agents.file_analysis_agent.run_scan"
        ) as mock_scan:
            task = TaskRequest(
                user_input="Analyze my project",
                intent=TaskIntent.FILE_ANALYSIS,
                parameters={"directory": "D:/Projects/Demo"},
            )

            response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    assert "unexpected internal error" in response.payload["error"].lower()
    mock_scan.assert_not_called()


def test_coordinator_keeps_request_rejected_when_rejection_audit_fails():
    registry = AgentRegistry()
    agent = FileAnalysisAgent()
    registry.register(agent)

    coordinator = create_coordinator(registry)

    coordinator.communication_policy.allowed_fields[
        "FileAnalysisAgent"
    ] = {"unauthorized_field"}

    with patch.object(
        coordinator.communication_audit,
        "record",
        side_effect=OSError("Audit storage unavailable"),
    ):
        with patch(
            "app.agents.file_analysis_agent.run_scan"
        ) as mock_scan:
            task = TaskRequest(
                user_input="Analyze my project",
                intent=TaskIntent.FILE_ANALYSIS,
                parameters={"directory": "D:/Projects/Demo"},
            )

            response = coordinator.handle_task(task)

    assert response.message_type == MessageType.ERROR
    mock_scan.assert_not_called()

def test_coordinator_recovers_after_planning_agent_exception():
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    original_process = agent.process

    with patch.object(
        agent,
        "process",
        side_effect=RuntimeError("Temporary processing failure"),
    ):
        failed_response = coordinator.handle_task(task)

    assert failed_response.sender == "Coordinator"
    assert failed_response.message_type == MessageType.ERROR

    with patch.object(
        agent,
        "process",
        side_effect=original_process,
    ):
        recovered_response = coordinator.handle_task(
            TaskRequest(
                user_input="Create a plan to analyze my project",
                intent=TaskIntent.PLAN_TASK,
            )
        )

    assert recovered_response.sender == "PlanningAgent"
    assert recovered_response.message_type == MessageType.RESULT
    assert recovered_response.signature is not None
    assert len(recovered_response.payload["steps"]) == 5

def test_coordinator_recovers_after_verification_agent_exception():
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    verification_agent = VerificationAgent()
    registry.register(verification_agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    original_process = verification_agent.process

    with patch.object(
        verification_agent,
        "process",
        side_effect=RuntimeError("Temporary verification failure"),
    ):
        failed_response = coordinator.handle_task(task)

    assert failed_response.sender == "Coordinator"
    assert failed_response.message_type == MessageType.ERROR

    with patch.object(
        verification_agent,
        "process",
        side_effect=original_process,
    ):
        recovered_response = coordinator.handle_task(
            TaskRequest(
                user_input="Create a plan to analyze my project",
                intent=TaskIntent.PLAN_TASK,
            )
        )

    assert recovered_response.sender == "PlanningAgent"
    assert recovered_response.message_type == MessageType.RESULT
    assert recovered_response.signature is not None
    assert len(recovered_response.payload["steps"]) == 5

def test_coordinator_recovers_after_unauthenticated_verification_response():
    registry = AgentRegistry()
    registry.register(create_planning_agent())

    verification_agent = VerificationAgent()
    registry.register(verification_agent)

    coordinator = create_coordinator(registry)

    task = TaskRequest(
        user_input="Create a project plan",
        intent=TaskIntent.PLAN_TASK,
    )

    original_process = verification_agent.process_authenticated

    with patch.object(
        verification_agent,
        "process_authenticated",
        side_effect=lambda message: AgentMessage(
            task_id=message.task_id,
            sender="VerificationAgent",
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload={"valid": True},
        ),
    ):
        failed_response = coordinator.handle_task(task)

    assert failed_response.sender == "Coordinator"
    assert failed_response.message_type == MessageType.ERROR
    assert "authentication failed" in failed_response.payload["error"].lower()

    with patch.object(
        verification_agent,
        "process_authenticated",
        side_effect=original_process,
    ):
        recovered_response = coordinator.handle_task(
            TaskRequest(
                user_input="Create a plan to analyze my project",
                intent=TaskIntent.PLAN_TASK,
            )
        )

    assert recovered_response.sender == "PlanningAgent"
    assert recovered_response.message_type == MessageType.RESULT
    assert recovered_response.signature is not None
    assert len(recovered_response.payload["steps"]) == 5

def test_coordinator_recovers_after_communication_audit_failure():
    registry = AgentRegistry()
    agent = FileAnalysisAgent()
    registry.register(agent)

    coordinator = create_coordinator(registry)

    original_record = coordinator.communication_audit.record

    with patch.object(
        coordinator.communication_audit,
        "record",
        side_effect=OSError("Temporary audit storage failure"),
    ):
        with patch(
            "app.agents.file_analysis_agent.run_scan"
        ) as mock_scan:
            failed_task = TaskRequest(
                user_input="Analyze my project",
                intent=TaskIntent.FILE_ANALYSIS,
                parameters={"directory": "D:/Projects/Demo"},
            )

            failed_response = coordinator.handle_task(failed_task)

            assert failed_response.message_type == MessageType.ERROR
            mock_scan.assert_not_called()

    with patch.object(
        coordinator.communication_audit,
        "record",
        side_effect=original_record,
    ):
        with patch(
            "app.agents.file_analysis_agent.run_scan"
        ) as mock_scan:
            mock_scan.return_value = {
                "root": "D:/Projects/Demo",
                "total_files": 5,
                "total_size_bytes": 1000,
                "extension_counts": {".py": 5},
                "duplicates": [],
                "recoverable_bytes": 0,
                "scan_warnings": [],
                "hash_skipped": 0,
            }

            recovered_response = coordinator.handle_task(
                TaskRequest(
                    user_input="Analyze my project",
                    intent=TaskIntent.FILE_ANALYSIS,
                    parameters={"directory": "D:/Projects/Demo"},
                )
            )

    assert recovered_response.sender == "FileAnalysisAgent"
    assert recovered_response.message_type == MessageType.RESULT
    assert recovered_response.signature is not None
    mock_scan.assert_called_once()

def test_coordinator_recovers_after_memory_database_failure(tmp_path):
    registry = AgentRegistry()
    agent = create_planning_agent()
    registry.register(agent)
    registry.register(VerificationAgent())

    from app.memory.database import SQLiteDatabase
    from app.memory.manager import MemoryManager
    from app.memory.repositories.episodic_memory import (
        EpisodicMemoryRepository,
    )

    database = SQLiteDatabase(tmp_path / "memory.db")
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

    coordinator = Coordinator(
        registry,
        create_test_authenticator(),
        memory_manager,
    )

    for agent_name in registry.list_agents():
        registry.get(agent_name).set_authenticator(
            coordinator.authenticator
        )

    original_remember_task = memory_manager.remember_task

    with patch.object(
        memory_manager,
        "remember_task",
        side_effect=sqlite3.OperationalError("Database unavailable."),
    ):
        failed_persistence_response = coordinator.handle_task(
            TaskRequest(
                user_input="Create a plan to analyze my project",
                intent=TaskIntent.PLAN_TASK,
            )
        )

    assert failed_persistence_response.sender == "PlanningAgent"
    assert failed_persistence_response.message_type == MessageType.RESULT
    assert failed_persistence_response.signature is not None

    with patch.object(
        memory_manager,
        "remember_task",
        side_effect=original_remember_task,
    ) as remember_mock:
        recovered_response = coordinator.handle_task(
            TaskRequest(
                user_input="Create a plan for my Python application",
                intent=TaskIntent.PLAN_TASK,
            )
        )

    assert recovered_response.sender == "PlanningAgent"
    assert recovered_response.message_type == MessageType.RESULT
    assert recovered_response.signature is not None
    assert len(recovered_response.payload["steps"]) == 5

    remember_mock.assert_called_once()
