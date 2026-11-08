
import logging
import sqlite3
from uuid import UUID

from app.agents.registry import AgentRegistry
from app.core.agent_auth import AgentAuthenticator
from app.core.communication_audit import CommunicationAudit
from app.core.communication_policy import CommunicationPolicy
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskIntent,
    TaskRequest,
)
from app.memory.context_builder import MemoryContextBuilder
from app.memory.manager import MemoryManager
from app.memory.procedural_context_builder import (
    ProceduralMemoryContextBuilder,
)
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.retention_policy import RetentionAssessment
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)
from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.semantic_context_builder import (
    SemanticMemoryContextBuilder,
)
from app.memory.working_context_builder import (
    WorkingMemoryContextBuilder,
)
from app.memory.working_manager import WorkingMemoryManager

logger = logging.getLogger(__name__)


class Coordinator:
    """Coordinates agent execution and controlled memory operations."""

    def __init__(
        self,
        registry: AgentRegistry,
        authenticator: AgentAuthenticator,
        memory_manager: MemoryManager | None = None,
        semantic_memory_manager: SemanticMemoryManager | None = None,
        procedural_memory_manager: ProceduralMemoryManager | None = None,
        working_memory_manager: WorkingMemoryManager | None = None,
    ):
        self.registry = registry
        self.authenticator = authenticator
        self.communication_policy = CommunicationPolicy()
        self.communication_audit = CommunicationAudit()

        self.memory_manager = memory_manager
        self.semantic_memory_manager = semantic_memory_manager
        self.procedural_memory_manager = procedural_memory_manager
        self.working_memory_manager = working_memory_manager

        self.memory_context_builder = (
            MemoryContextBuilder(memory_manager)
            if memory_manager is not None
            else None
        )

        self.semantic_context_builder = (
            SemanticMemoryContextBuilder(semantic_memory_manager)
            if semantic_memory_manager is not None
            else None
        )

        self.procedural_context_builder = (
            ProceduralMemoryContextBuilder(procedural_memory_manager)
            if procedural_memory_manager is not None
            else None
        )

        self.working_context_builder = (
            WorkingMemoryContextBuilder(working_memory_manager)
            if working_memory_manager is not None
            else None
        )

        self.routes = {
            TaskIntent.FILE_ANALYSIS: "FileAnalysisAgent",
            TaskIntent.PLAN_TASK: "PlanningAgent",
        }

    def assess_memory_retention(
        self,
        limit: int = 100,
    ) -> list[tuple[EpisodicMemoryRecord, RetentionAssessment]]:
        """Return retention assessments for coordinator review."""

        if self.memory_manager is None:
            return []

        assessments = self.memory_manager.assess_retention(
            requesting_agent="CoordinatorAgent",
            limit=limit,
        )

        eligible_count = sum(
            assessment.eligible
            for _, assessment in assessments
        )

        logger.info(
            "Memory retention assessment completed: "
            "%d records reviewed, %d eligible for archival.",
            len(assessments),
            eligible_count,
        )

        return assessments

    def archive_memory(self, task_id: UUID) -> bool:
        """Archive an eligible memory through an explicit coordinator request."""

        if self.memory_manager is None:
            raise RuntimeError("Memory manager is not initialized.")

        logger.info("Memory archival requested for task %s.", task_id)

        try:
            archived = self.memory_manager.archive_task(
                task_id,
                requesting_agent="CoordinatorAgent",
            )

            if archived:
                logger.info(
                    "Memory successfully archived for task %s.",
                    task_id,
                )
            else:
                logger.warning(
                    "Memory archival was not completed for task %s.",
                    task_id,
                )

            return archived

        except Exception:
            logger.exception(
                "Memory archival failed for task %s.",
                task_id,
            )
            raise

    def restore_memory(self, task_id: UUID) -> bool:
        """Restore an archived memory through an explicit coordinator request."""

        if self.memory_manager is None:
            raise RuntimeError("Memory manager is not initialized.")

        logger.info("Memory restoration requested for task %s.", task_id)

        try:
            restored = self.memory_manager.restore_task(
                task_id,
                requesting_agent="CoordinatorAgent",
            )

            if restored:
                logger.info(
                    "Memory successfully restored for task %s.",
                    task_id,
                )
            else:
                logger.warning(
                    "Memory restoration was not completed for task %s.",
                    task_id,
                )

            return restored

        except Exception:
            logger.exception(
                "Memory restoration failed for task %s.",
                task_id,
            )
            raise

    def handle_task(self, task: TaskRequest) -> AgentMessage:
        """Routes, executes, verifies, and records an agent task."""

        agent_name = None

        try:
            agent_name = self.routes.get(task.intent)

            if agent_name is None:
                raise ValueError(
                    f"Unsupported task intent: {task.intent}"
                )

            if task.intent == TaskIntent.FILE_ANALYSIS:
                directory = task.parameters.get("directory")

                if (
                    not isinstance(directory, str)
                    or not directory.strip()
                ):
                    raise ValueError(
                        "A valid directory parameter is required."
                    )

                payload = {"directory": directory}

            elif task.intent == TaskIntent.PLAN_TASK:
                payload = {"objective": task.user_input}

            else:
                raise ValueError(
                    f"Unsupported task intent: {task.intent}"
                )

            agent = self.registry.get(agent_name)

            memory_context = self._build_memory_context(
                task,
                agent_name,
            )
            semantic_context = self._build_semantic_context(
                task,
                agent_name,
            )
            procedural_context = self._build_procedural_context(
                task,
                agent_name,
            )
            working_context = self._build_working_context(
                task,
                agent_name,
            )

            request = AgentMessage(
                task_id=task.task_id,
                sender="Coordinator",
                recipient=agent_name,
                message_type=MessageType.TASK,
                payload=payload,
                memory_context=memory_context,
                semantic_context=semantic_context,
                procedural_context=procedural_context,
                working_memory_context=working_context,
            )

            self._send_request(request)

            response = agent.process(request)

            self._validate_agent_response(
                response,
                agent_name,
                task.task_id,
                request.message_id,
            )

            signed_response = self.authenticator.sign(
                response,
                expected_sender=agent_name,
            )

            if not self.authenticator.verify(signed_response):
                raise ValueError(
                    "Agent response authentication failed."
                )

            if (
                task.intent == TaskIntent.PLAN_TASK
                and signed_response.message_type == MessageType.RESULT
            ):
                self._verify_plan(task, signed_response)

            self._remember_task(
                task,
                agent_name,
                signed_response,
            )

            return signed_response

        except (ValueError, PermissionError) as error:
            failure = self._create_error_response(
                task,
                str(error),
            )

            if agent_name is not None:
                self._remember_task(task, agent_name, failure)

            return failure

        except Exception:
            logger.exception(
                "Unexpected error while processing task %s.",
                task.task_id,
            )

            failure = self._create_error_response(
                task,
                "An unexpected internal error occurred while processing the task.",
            )

            if agent_name is not None:
                self._remember_task(task, agent_name, failure)

            return failure

    def _build_memory_context(
        self,
        task: TaskRequest,
        recipient_agent: str,
    ):
        """Builds authorized episodic memory context."""

        if self.memory_context_builder is None:
            return None

        try:
            objective = (
                task.user_input
                if task.intent == TaskIntent.PLAN_TASK
                else None
            )

            return self.memory_context_builder.build_context(
                task_id=task.task_id,
                intent=task.intent.value,
                recipient_agent=recipient_agent,
                objective=objective,
            )

        except PermissionError:
            raise

        except sqlite3.Error:
            logger.warning(
                "Episodic memory database unavailable; "
                "proceeding without context."
            )
            return None

    def _build_semantic_context(
        self,
        task: TaskRequest,
        recipient_agent: str,
    ):
        """Builds authorized semantic memory context for planning tasks."""

        if (
            self.semantic_context_builder is None
            or task.intent != TaskIntent.PLAN_TASK
        ):
            return None

        try:
            return self.semantic_context_builder.build_context(
                task_id=task.task_id,
                objective=task.user_input,
                recipient_agent=recipient_agent,
            )

        except PermissionError:
            raise

        except sqlite3.Error:
            logger.warning(
                "Semantic memory database unavailable; "
                "proceeding without context."
            )
            return None

    def _build_procedural_context(
        self,
        task: TaskRequest,
        recipient_agent: str,
    ):
        """Builds authorized procedural memory context for planning tasks."""

        if (
            self.procedural_context_builder is None
            or task.intent != TaskIntent.PLAN_TASK
        ):
            return None

        try:
            return self.procedural_context_builder.build_context(
                task_id=task.task_id,
                objective=task.user_input,
                recipient_agent=recipient_agent,
            )

        except PermissionError:
            raise

        except sqlite3.Error:
            logger.warning(
                "Procedural memory database unavailable; "
                "proceeding without context."
            )
            return None

    def _build_working_context(
        self,
        task: TaskRequest,
        recipient_agent: str,
    ):
        """Builds isolated working memory context for the current task."""

        if self.working_context_builder is None:
            return None

        try:
            return self.working_context_builder.build_context(
                task_id=task.task_id,
                recipient_agent=recipient_agent,
            )

        except PermissionError:
            raise

        except sqlite3.Error:
            logger.warning(
                "Working memory database unavailable; "
                "proceeding without context."
            )
            return None

    def _send_request(self, request: AgentMessage) -> None:
        """Validates and audits outgoing agent communication."""

        try:
            self.communication_policy.validate_outgoing(request)

        except ValueError as error:
            self.communication_audit.record(
                request,
                outcome="rejected",
                reason=str(error),
            )
            raise

        self.communication_audit.record(
            request,
            outcome="accepted",
        )

    @staticmethod
    def _validate_agent_response(
        response: AgentMessage,
        expected_sender: str,
        expected_task_id,
        expected_message_id,
    ) -> None:
        """Validates agent identity and response correlation."""

        if response.sender != expected_sender:
            raise ValueError("Agent identity mismatch.")

        if response.task_id != expected_task_id:
            raise ValueError("Agent task ID mismatch.")

        if response.recipient != "Coordinator":
            raise ValueError("Unexpected response recipient.")

        if response.in_reply_to != expected_message_id:
            raise ValueError("Agent response correlation mismatch.")

        if response.message_type not in {
            MessageType.RESULT,
            MessageType.ERROR,
        }:
            raise ValueError("Unexpected agent response type.")

    def _verify_plan(
        self,
        task: TaskRequest,
        planning_response: AgentMessage,
    ) -> None:
        """Requires independent verification before accepting a plan."""

        verification_agent_name = "VerificationAgent"
        verification_agent = self.registry.get(
            verification_agent_name
        )

        verification_context = self._build_memory_context(
            task,
            verification_agent_name,
        )
        semantic_context = self._build_semantic_context(
            task,
            verification_agent_name,
        )
        procedural_context = self._build_procedural_context(
            task,
            verification_agent_name,
        )
        working_context = self._build_working_context(
            task,
            verification_agent_name,
        )

        verification_request = AgentMessage(
            task_id=task.task_id,
            sender="Coordinator",
            recipient=verification_agent_name,
            message_type=MessageType.TASK,
            payload={
                "planning_result": planning_response.model_dump(
                    mode="json"
                )
            },
            memory_context=verification_context,
            semantic_context=semantic_context,
            procedural_context=procedural_context,
            working_memory_context=working_context,
        )

        self._send_request(verification_request)

        verification_response = verification_agent.process(
            verification_request
        )

        self._validate_agent_response(
            verification_response,
            verification_agent_name,
            task.task_id,
            verification_request.message_id,
        )

        signed_verification = self.authenticator.sign(
            verification_response,
            expected_sender=verification_agent_name,
        )

        if not self.authenticator.verify(signed_verification):
            raise ValueError(
                "Verification response authentication failed."
            )

        if signed_verification.message_type != MessageType.RESULT:
            raise ValueError(
                "VerificationAgent did not return a valid result."
            )

        report = signed_verification.payload

        if not isinstance(report, dict):
            raise ValueError("Invalid verification report.")

        if type(report.get("valid")) is not bool:
            raise ValueError(
                "Verification report has an invalid status."
            )

        if report["valid"] is not True:
            raise ValueError(
                "Planning result failed verification."
            )

        if report.get("source_agent") != "PlanningAgent":
            raise ValueError(
                "Verification report source mismatch."
            )

        if report.get("task_id") != str(task.task_id):
            raise ValueError(
                "Verification report task ID mismatch."
            )

        errors = report.get("errors")

        if type(errors) is not list or errors:
            raise ValueError(
                "Verification report contains errors."
            )

    @staticmethod
    def _create_error_response(
        task: TaskRequest,
        error: str,
    ) -> AgentMessage:
        """Creates a controlled error response for the user."""

        return AgentMessage(
            task_id=task.task_id,
            sender="Coordinator",
            recipient="User",
            message_type=MessageType.ERROR,
            payload={"error": error},
        )

    def _remember_task(
        self,
        task: TaskRequest,
        agent_name: str,
        response: AgentMessage,
    ) -> None:
        """Persists a concise task outcome without storing raw payloads."""

        if self.memory_manager is None:
            return

        if response.message_type == MessageType.ERROR:
            status = MemoryStatus.FAILED
            summary = f"{agent_name} task failed."

        elif response.message_type == MessageType.RESULT:
            status = MemoryStatus.COMPLETED

            if agent_name == "FileAnalysisAgent":
                total_files = response.payload.get("total_files")
                duplicate_groups = response.payload.get(
                    "duplicate_groups"
                )

                if (
                    type(total_files) is not int
                    or total_files < 0
                    or type(duplicate_groups) is not int
                    or duplicate_groups < 0
                ):
                    return

                summary = (
                    f"File analysis completed: {total_files} files scanned; "
                    f"{duplicate_groups} duplicate groups found."
                )

            elif agent_name == "PlanningAgent":
                steps = response.payload.get("steps")

                if (
                    not isinstance(steps, list)
                    or not all(isinstance(step, str) for step in steps)
                ):
                    return

                summary = (
                    f"Planning completed: generated a plan "
                    f"with {len(steps)} steps."
                )

            else:
                return

        else:
            return

        record = EpisodicMemoryRecord(
            task_id=task.task_id,
            intent=task.intent.value,
            status=status,
            agent_name=agent_name,
            summary=summary,
            created_at=task.created_at,
        )

        try:
            self.memory_manager.remember_task(record)

        except Exception:
            logger.exception(
                "Task memory could not be persisted for task %s.",
                task.task_id,
            )
