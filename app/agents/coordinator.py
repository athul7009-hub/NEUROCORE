from app.core.communication_audit import CommunicationAudit
from app.core.communication_policy import CommunicationPolicy
from app.agents.registry import AgentRegistry
from app.core.agent_auth import AgentAuthenticator
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskIntent,
    TaskRequest,
)
import logging
from app.memory.manager import MemoryManager
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryStatus,
)

logger = logging.getLogger(__name__)

class Coordinator:
    def __init__(
        self,
        registry: AgentRegistry,
        authenticator: AgentAuthenticator,
        memory_manager: MemoryManager | None = None,
    ):
        self.registry = registry
        self.authenticator = authenticator
        self.communication_policy = CommunicationPolicy()
        self.communication_audit = CommunicationAudit()
        self.memory_manager = memory_manager
        self.routes = {
            TaskIntent.FILE_ANALYSIS: "FileAnalysisAgent",
            TaskIntent.PLAN_TASK: "PlanningAgent",
        }

    def handle_task(self, task: TaskRequest) -> AgentMessage:
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

            request = AgentMessage(
                task_id=task.task_id,
                sender="Coordinator",
                recipient=agent_name,
                message_type=MessageType.TASK,
                payload=payload,
            )
             # Enforce selective communication policy.
                        # Enforce selective communication policy.
            try:
                self.communication_policy.validate_outgoing(request)

            except ValueError as error:
                self.communication_audit.record(
                    request,
                    outcome="rejected",
                    reason=str(error),
                )
                raise

            # Record policy-approved outgoing communication.
            self.communication_audit.record(
                request,
                outcome="accepted",
            )

            # Deliver the validated request to the agent.
            response = agent.process(request)
            # Validate the response against the registered agent.
            if response.sender != agent_name:
                raise ValueError("Agent identity mismatch.")

            if response.task_id != task.task_id:
                raise ValueError("Agent task ID mismatch.")

            if response.recipient != "Coordinator":
                raise ValueError("Unexpected response recipient.")

            if response.in_reply_to != request.message_id:
                raise ValueError("Agent response correlation mismatch.")

            if response.message_type not in {
                MessageType.RESULT,
                MessageType.ERROR,
            }:
                raise ValueError("Unexpected agent response type.")

            # Sign using the trusted runtime's registered identity.
            signed_response = self.authenticator.sign(
                response,
                expected_sender=agent_name,
            )

            # Verify before accepting the response.
            if not self.authenticator.verify(signed_response):
                raise ValueError("Agent response authentication failed.")

            self._remember_task(task, agent_name, signed_response)

            return signed_response

        except ValueError as error:
            return AgentMessage(
                task_id=task.task_id,
                sender="Coordinator",
                recipient="User",
                message_type=MessageType.ERROR,
                payload={"error": str(error)},
            )
    def _remember_task(
        self,
        task: TaskRequest,
        agent_name: str,
        response: AgentMessage,
    ) -> None:
        if self.memory_manager is None:
            return

        if response.message_type == MessageType.ERROR:
            status = MemoryStatus.FAILED
            summary = f"{agent_name} task failed."

        elif response.message_type == MessageType.RESULT:
            status = MemoryStatus.COMPLETED

            if agent_name == "FileAnalysisAgent":
                total_files = response.payload.get("total_files")
                duplicate_groups = response.payload.get("duplicate_groups")

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
            logger.warning(
                "Task memory could not be persisted; "
                "the agent response will still be returned."
            )
