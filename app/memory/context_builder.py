
from uuid import UUID

from app.memory.context_schemas import (
    MemoryContext,
    MemoryContextItem,
)
from app.memory.manager import MemoryManager
from app.memory.relevance_evaluator import MemoryRelevanceEvaluator


class MemoryContextBuilder:
    """Builds bounded, relevant memory context for agents."""

    MAX_MEMORIES = 10
    CANDIDATE_LIMIT = 50

    def __init__(self, memory_manager: MemoryManager):
        self.memory_manager = memory_manager
        self.relevance_evaluator = MemoryRelevanceEvaluator()

    def build_context(
        self,
        task_id: UUID,
        intent: str,
        recipient_agent: str,
        limit: int = 5,
        objective: str | None = None,
    ) -> MemoryContext:
        """Retrieves authorized candidates and selects relevant memories."""

        if not isinstance(task_id, UUID):
            raise TypeError("Task ID must be a UUID.")

        if not isinstance(intent, str) or not intent.strip():
            raise ValueError("A valid task intent is required.")

        if (
            not isinstance(recipient_agent, str)
            or not recipient_agent.strip()
        ):
            raise ValueError("A valid recipient agent is required.")

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Memory limit must be an integer.")

        if not 1 <= limit <= self.MAX_MEMORIES:
            raise ValueError(
                f"Memory limit must be between 1 and {self.MAX_MEMORIES}."
            )

        if objective is not None and (
            not isinstance(objective, str) or not objective.strip()
        ):
            raise ValueError("A valid objective is required.")

        records = self.memory_manager.get_recent_tasks(
            limit=self.CANDIDATE_LIMIT,
            requesting_agent=recipient_agent,
            intent=intent.strip(),
        )

        memories = [
            MemoryContextItem(
                source_task_id=record.task_id,
                intent=record.intent,
                status=record.status,
                agent_name=record.agent_name,
                summary=record.summary,
                completed_at=record.completed_at,
            )
            for record in records
            if record.task_id != task_id
        ]

        if objective is not None:
            evaluation = self.relevance_evaluator.evaluate(
                objective=objective.strip(),
                memories=memories,
            )
            memories = evaluation.selected_memories

        return MemoryContext(
            task_id=task_id,
            recipient_agent=recipient_agent,
            memories=memories[:limit],
        )
