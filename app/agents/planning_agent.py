
from app.agents.base_agent import BaseAgent
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskPlan,
)
from app.memory.relevance_evaluator import MemoryRelevanceEvaluator
from app.memory.schemas import MemoryStatus


class PlanningAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="PlanningAgent",
            description="Creates structured plans for supported tasks.",
        )
        self.memory_evaluator = MemoryRelevanceEvaluator()

    def process(self, message: AgentMessage) -> AgentMessage:
        try:
            objective = message.payload.get("objective")

            if not isinstance(objective, str) or not objective.strip():
                raise ValueError("A valid task objective is required.")

            metadata = {}
            steps = [
                "Validate the requested project directory.",
                "Verify that the directory is approved for scanning.",
                "Scan the directory and collect file metadata.",
                "Analyze duplicate files and file distribution.",
                "Prepare a summary of the analysis results.",
            ]

            memory_context = message.memory_context

            if memory_context is not None:
                if memory_context.task_id != message.task_id:
                    raise ValueError("Memory context task ID mismatch.")

                if memory_context.recipient_agent != self.name:
                    raise ValueError("Memory context recipient mismatch.")

                evaluation = self.memory_evaluator.evaluate(
                    objective=objective.strip(),
                    memories=memory_context.memories,
                )

                selected_memories = evaluation.selected_memories

                completed_count = sum(
                    memory.status == MemoryStatus.COMPLETED
                    for memory in selected_memories
                )

                failed_count = sum(
                    memory.status == MemoryStatus.FAILED
                    for memory in selected_memories
                )

                # Use successful historical experience.
                if completed_count:
                    steps.insert(
                        0,
                        "Consider applicable practices from relevant previously completed tasks.",
                    )

                # Add preventive checks based on historical failures.
                if failed_count:
                    steps.append(
                        "Include preventive checks informed by relevant previously failed tasks.",
                    )

                metadata["memory_evaluation"] = (
                    evaluation.model_dump(mode="json")
                )

                metadata["memory_influence"] = {
                    "selected_count": len(selected_memories),
                    "completed_count": completed_count,
                    "failed_count": failed_count,
                }

            plan = TaskPlan(
                task_id=message.task_id,
                objective=objective.strip(),
                steps=steps,
            )

            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.RESULT,
                payload=plan.model_dump(mode="json"),
                metadata=metadata,
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
