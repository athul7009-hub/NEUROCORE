
import json

from app.agents.base_agent import BaseAgent
from app.core.schemas import AgentMessage, MessageType, TaskPlan
from app.llm.ollama_client import OllamaError
from app.llm.reasoning import ReasoningError, ReasoningService
from app.llm.schemas import ReasoningRequest
from app.memory.relevance_evaluator import MemoryRelevanceEvaluator
from app.memory.schemas import MemoryStatus


class PlanningAgent(BaseAgent):
    MAX_CONTEXT_LENGTH = 12000

    def __init__(
        self,
        reasoning_service: ReasoningService | None = None,
    ):
        super().__init__(
            name="PlanningAgent",
            description="Creates structured plans for supported tasks.",
        )
        self.memory_evaluator = MemoryRelevanceEvaluator()
        self.reasoning_service = reasoning_service or ReasoningService()

    def _build_reasoning_context(
        self,
        message: AgentMessage,
        selected_memories: list,
    ) -> str:
        context = {}

        if selected_memories:
            context["episodic"] = [
                {
                    "intent": memory.intent,
                    "status": memory.status.value,
                    "agent_name": memory.agent_name,
                    "summary": memory.summary,
                }
                for memory in selected_memories
            ]

        if message.semantic_context:
            context["semantic"] = [
                {
                    "subject": memory.subject,
                    "predicate": memory.predicate,
                    "object": memory.object,
                    "confidence": memory.confidence,
                }
                for memory in message.semantic_context.memories
            ]

        if message.procedural_context:
            context["procedural"] = [
                {
                    "name": procedure.name,
                    "description": procedure.description,
                    "when_to_use": procedure.when_to_use,
                    "confidence": procedure.confidence,
                    "steps": [
                        {
                            "step_number": step.step_number,
                            "instruction": step.instruction,
                            "expected_outcome": step.expected_outcome,
                        }
                        for step in procedure.steps
                    ],
                }
                for procedure in message.procedural_context.memories
            ]

        if message.working_memory_context:
            context["working"] = [
                {
                    "key": entry.key,
                    "entry_type": entry.entry_type.value,
                    "content": entry.content,
                    "source_agent": entry.source_agent,
                }
                for entry in message.working_memory_context.entries
            ]

        if message.prospective_context:
            context["prospective"] = [
                {
                    "title": intention.title,
                    "description": intention.description,
                    "action": intention.action,
                    "trigger_type": intention.trigger_type.value,
                    "trigger_condition": intention.trigger_condition,
                    "priority": intention.priority.value,
                    "status": intention.status.value,
                    "due_at": (
                        intention.due_at.isoformat()
                        if intention.due_at
                        else None
                    ),
                }
                for intention in message.prospective_context.memories
            ]

        if not context:
            return ""

        serialized_context = json.dumps(
            context,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        if len(serialized_context) > self.MAX_CONTEXT_LENGTH:
            raise ValueError(
                "Combined memory context exceeds the reasoning context limit."
            )

        return serialized_context

    def process(self, message: AgentMessage) -> AgentMessage:
        try:
            objective = message.payload.get("objective")

            if not isinstance(objective, str) or not objective.strip():
                raise ValueError("A valid task objective is required.")

            objective = objective.strip()
            metadata = {}
            selected_memories = []

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

                metadata["memory_evaluation"] = (
                    evaluation.model_dump(mode="json")
                )
                metadata["memory_influence"] = {
                    "selected_count": len(selected_memories),
                    "completed_count": completed_count,
                    "failed_count": failed_count,
                }

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

                metadata["semantic_memory_influence"] = {
                    "selected_count": len(semantic_context.memories),
                }

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

                metadata["procedural_memory_influence"] = {
                    "selected_count": len(procedural_context.memories),
                    "procedure_names": [
                        procedure.name
                        for procedure in procedural_context.memories
                    ],
                }

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

                metadata["working_memory_influence"] = {
                    "selected_count": len(working_context.entries),
                }

            prospective_context = message.prospective_context

            if prospective_context is not None:
                if prospective_context.task_id != message.task_id:
                    raise ValueError(
                        "Prospective memory context task ID mismatch."
                    )
                if prospective_context.recipient_agent != self.name:
                    raise ValueError(
                        "Prospective memory context recipient mismatch."
                    )

                metadata["prospective_memory_influence"] = {
                    "selected_count": len(prospective_context.memories),
                }

            reasoning_context = self._build_reasoning_context(
                message,
                selected_memories,
            )

            reasoning_request = ReasoningRequest(
                task_id=message.task_id,
                agent_name=self.name,
                objective=objective,
                context=reasoning_context,
            )

            reasoning_response = self.reasoning_service.generate(
                reasoning_request
            )

            plan = TaskPlan(
                task_id=message.task_id,
                objective=objective,
                steps=reasoning_response.proposed_steps,
                requires_approval=True,
            )

            metadata["reasoning"] = {
                "request_id": str(reasoning_response.request_id),
                "model_generated": True,
                "confidence": reasoning_response.confidence,
                "limitations": reasoning_response.limitations,
            }

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

        except (ReasoningError, OllamaError):
            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                payload={
                    "error": (
                        "Local reasoning failed. "
                        "The planning proposal could not be generated."
                    )
                },
                in_reply_to=message.message_id,
            )