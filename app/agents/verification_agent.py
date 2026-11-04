
from app.agents.base_agent import BaseAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan


class VerificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="VerificationAgent",
            description="Validates structured outputs returned by other agents."
        )

    def process(self, message: AgentMessage) -> AgentMessage:
        errors = []

        # Validate the source agent.
        if message.sender != "PlanningAgent":
            errors.append("Unexpected source agent.")

        # Validate the message type.
        if message.message_type == MessageType.ERROR:
            errors.append("The source agent returned an error.")

        elif message.message_type != MessageType.RESULT:
            errors.append("Message is not a RESULT message.")

        if message.task_id is None:
            errors.append("Task ID is missing.")

        plan = None

        # Validate the TaskPlan structure.
        if not errors:
            try:
                plan = TaskPlan.model_validate(message.payload)

            except (ValueError, TypeError) as error:
                errors.append(f"Invalid task plan: {error}")

        # Verify task ID consistency.
        if plan is not None and plan.task_id != message.task_id:
            errors.append("Task ID mismatch between plan and message.")

        report = {
            "valid": not errors,
            "source_agent": message.sender,
            "task_id": str(message.task_id),
            "errors": errors,
        }

        return AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient=message.sender,
            message_type=MessageType.RESULT,
            payload=report,
            in_reply_to=message.message_id,
        )
