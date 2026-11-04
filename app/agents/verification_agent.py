
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

        if message.sender != "PlanningAgent":
            errors.append("Unexpected source agent.")

        if message.message_type == MessageType.ERROR:
            errors.append("The source agent returned an error.")
        elif message.message_type != MessageType.RESULT:
            errors.append("The source message is not a result.")

        if not errors:
            try:
                plan = TaskPlan.model_validate(message.payload)

                if plan.task_id != message.task_id:
                    errors.append(
                        "Task ID mismatch between message and plan."
                    )

            except (ValueError, TypeError) as error:
                errors.append(f"Invalid task plan: {error}")

        return AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient=message.sender,
            message_type=MessageType.RESULT,
            payload={
                "valid": not errors,
                "source_agent": message.sender,
                "task_id": str(message.task_id),
                "errors": errors,
            },
            in_reply_to=message.message_id,
        )
