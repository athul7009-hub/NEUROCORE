
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

            objective = objective.strip()
            metadata = {}

            steps = [
                "Validate the requested project directory.",
                "Verify that the directory is approved for scanning.",
                "Scan the directory and collect file metadata.",
                "Analyze duplicate files and file distribution.",
                "Prepare a summary of the analysis results.",
            ]

            # Evaluate episodic memory context.
            memory_context = message.memory_context

            if memory_context is not None:
                if memory_context.task_id != message.task_id:
                    raise ValueError("Memory context task ID mismatch.")

                if memory_context.recipient_agent != self.name:
                    raise ValueError("Memory context recipient mismatch.")

                evaluation = self.memory_evaluator.evaluate(
                    objective=objective,
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

                if completed_count:
                    steps.insert(
                        0,
                        "Consider applicable practices from relevant previously completed tasks.",
                    )

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

            # Validate semantic memory context.
            semantic_context = message.semantic_context

            if semantic_context is not None:
                if semantic_context.task_id != message.task_id:
                    raise ValueError(
                        "Semantic memory context task ID mismatch."
                    )

                if semantic_context.recipient_agent != self.name:
                    raise ValueError(
                        "Semantic memory context recipient mismatch."
                    )

                semantic_memory_count = len(semantic_context.memories)

                if semantic_memory_count:
                    steps.insert(
                        0,
                        "Consider relevant validated semantic knowledge when preparing the plan.",
                    )

                metadata["semantic_memory_influence"] = {
                    "selected_count": semantic_memory_count,
                }

            # Validate and apply procedural memory context.
            procedural_context = message.procedural_context

            if procedural_context is not None:
                if procedural_context.task_id != message.task_id:
                    raise ValueError(
                        "Procedural memory context task ID mismatch."
                    )

                if procedural_context.recipient_agent != self.name:
                    raise ValueError(
                        "Procedural memory context recipient mismatch."
                    )

                selected_procedures = procedural_context.memories

                if selected_procedures:
                    steps.insert(
                        0,
                        "Apply relevant validated procedures where their usage conditions match this task.",
                    )

                    procedure_steps = []

                    for procedure in selected_procedures:
                        procedure_steps.append(
                            f"Apply procedure '{procedure.name}': "
                            f"{procedure.description}"
                        )

                        for procedure_step in procedure.steps[:3]:
                            procedure_steps.append(
                                f"Procedure guidance: "
                                f"{procedure_step.instruction}"
                            )

                    steps[0:0] = procedure_steps[:10]

                metadata["procedural_memory_influence"] = {
                    "selected_count": len(selected_procedures),
                    "procedure_names": [
                        procedure.name
                        for procedure in selected_procedures
                    ],
                }

            # Validate task-scoped working memory context.
            working_context = message.working_memory_context

            if working_context is not None:
                if working_context.task_id != message.task_id:
                    raise ValueError(
                        "Working memory context task ID mismatch."
                    )

                if working_context.recipient_agent != self.name:
                    raise ValueError(
                        "Working memory context recipient mismatch."
                    )

                working_entry_count = len(working_context.entries)

                if working_entry_count:
                    steps.insert(
                        0,
                        "Review relevant current-task observations and intermediate results before finalizing the plan.",
                    )

                metadata["working_memory_influence"] = {
                    "selected_count": working_entry_count,
                }

            plan = TaskPlan(
                task_id=message.task_id,
                objective=objective,
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
