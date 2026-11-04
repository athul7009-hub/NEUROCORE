
from app.agents.base_agent import BaseAgent
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskPlan,
)


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PlanningAgent",
            description="Creates structured plans for supported tasks."
        )

    def process(self, message: AgentMessage) -> AgentMessage:
        try:
            objective = message.payload.get("objective")

            if not isinstance(objective, str) or not objective.strip():
                raise ValueError("A valid task objective is required.")

            plan = TaskPlan(
                task_id=message.task_id,
                objective=objective.strip(),
                steps=[
                    "Validate the requested project directory.",
                    "Verify that the directory is approved for scanning.",
                    "Scan the directory and collect file metadata.",
                    "Analyze duplicate files and file distribution.",
                    "Prepare a summary of the analysis results.",
                ],
            )

            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.RESULT,
                payload=plan.model_dump(mode="json"),
                in_reply_to=message.message_id,
            )

        except ValueError as error:
            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                payload={"error": str(error)},
                in_reply_to=message.message_id,
            )
