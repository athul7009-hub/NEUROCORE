
from app.agents.base_agent import BaseAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan
from app.memory.relevance_evaluator import MemoryRelevanceEvaluator


class VerificationAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="VerificationAgent",
            description="Validates structured outputs returned by other agents.",
        )
        self.memory_evaluator = MemoryRelevanceEvaluator()

    def process(self, message: AgentMessage) -> AgentMessage:
        errors = []
        metadata = {}

        # Validate the Coordinator request.
        if message.sender != "Coordinator":
            errors.append("Unexpected request sender.")

        if message.recipient != self.name:
            errors.append("Unexpected request recipient.")

        if message.message_type != MessageType.TASK:
            errors.append("Message is not a TASK request.")

        planning_result = None

        # Extract the embedded PlanningAgent response.
        if not errors:
            try:
                planning_result = AgentMessage.model_validate(
                    message.payload["planning_result"]
                )
            except (KeyError, TypeError, ValueError):
                errors.append("Missing or invalid planning result.")

        plan = None

        if planning_result is not None:
            if planning_result.sender != "PlanningAgent":
                errors.append("Unexpected source agent.")

            if planning_result.recipient != "Coordinator":
                errors.append("Unexpected planning response recipient.")

            if planning_result.message_type == MessageType.ERROR:
                errors.append("The source agent returned an error.")

            elif planning_result.message_type != MessageType.RESULT:
                errors.append("Planning response is not a RESULT message.")

            if planning_result.task_id != message.task_id:
                errors.append(
                    "Task ID mismatch between request and planning response."
                )

            if not planning_result.in_reply_to:
                errors.append("Planning response correlation is missing.")

            if not planning_result.signature:
                errors.append("Planning response authentication is missing.")

            if not errors:
                try:
                    plan = TaskPlan.model_validate(
                        planning_result.payload
                    )
                except (ValueError, TypeError):
                    errors.append("Invalid task plan.")

            if plan is not None and plan.task_id != planning_result.task_id:
                errors.append("Task ID mismatch between plan and message.")

        # Validate and evaluate optional episodic memory context.
        memory_context = message.memory_context

        if memory_context is not None:
            if memory_context.task_id != message.task_id:
                errors.append("Memory context task ID mismatch.")

            elif memory_context.recipient_agent != self.name:
                errors.append("Memory context recipient mismatch.")

            else:
                try:
                    evaluation = self.memory_evaluator.evaluate(
                        objective=(
                            "Verify agent outputs, validate task plans, "
                            "check structured data, and detect inconsistencies."
                        ),
                        memories=memory_context.memories,
                    )

                    metadata["memory_evaluation"] = (
                        evaluation.model_dump(mode="json")
                    )

                except (ValueError, TypeError):
                    errors.append("Memory evaluation failed.")

        # Validate optional semantic memory context.
        semantic_context = message.semantic_context

        if semantic_context is not None:
            if semantic_context.task_id != message.task_id:
                errors.append("Semantic memory context task ID mismatch.")

            elif semantic_context.recipient_agent != self.name:
                errors.append("Semantic memory context recipient mismatch.")

            else:
                metadata["semantic_memory_context"] = {
                    "selected_count": len(semantic_context.memories),
                }

        # Validate optional procedural memory context.
        procedural_context = message.procedural_context

        if procedural_context is not None:
            if procedural_context.task_id != message.task_id:
                errors.append(
                    "Procedural memory context task ID mismatch."
                )

            elif procedural_context.recipient_agent != self.name:
                errors.append(
                    "Procedural memory context recipient mismatch."
                )

            else:
                metadata["procedural_memory_context"] = {
                    "selected_count": len(procedural_context.memories),
                }

        # Validate optional task-scoped working memory context.
        working_context = message.working_memory_context

        if working_context is not None:
            if working_context.task_id != message.task_id:
                errors.append(
                    "Working memory context task ID mismatch."
                )

            elif working_context.recipient_agent != self.name:
                errors.append(
                    "Working memory context recipient mismatch."
                )

            else:
                metadata["working_memory_context"] = {
                    "selected_count": len(working_context.entries),
                }

        # Validate optional prospective memory context.
        prospective_context = message.prospective_context

        if prospective_context is not None:
            if prospective_context.task_id != message.task_id:
                errors.append(
                    "Prospective memory context task ID mismatch."
                )

            elif prospective_context.recipient_agent != self.name:
                errors.append(
                    "Prospective memory context recipient mismatch."
                )

            else:
                metadata["prospective_memory_context"] = {
                    "selected_count": len(prospective_context.memories),
                }

        report = {
            "valid": not errors,
            "source_agent": (
                planning_result.sender if planning_result else None
            ),
            "task_id": str(message.task_id),
            "errors": errors,
        }

        return AgentMessage(
            task_id=message.task_id,
            sender=self.name,
            recipient="Coordinator",
            message_type=MessageType.RESULT,
            payload=report,
            metadata=metadata,
            in_reply_to=message.message_id,
        )
