
from uuid import UUID

from app.memory.working_manager import WorkingMemoryManager
from app.memory.working_schemas import (
    WorkingMemoryContext,
    WorkingMemoryContextItem,
)


class WorkingMemoryContextBuilder:
    """Builds isolated, bounded working context for an agent."""

    MAX_CONTEXT_ITEMS = 20

    def __init__(self, manager: WorkingMemoryManager):
        if not isinstance(manager, WorkingMemoryManager):
            raise TypeError("A valid WorkingMemoryManager is required.")

        self.manager = manager

    def build_context(
        self,
        *,
        task_id: UUID,
        recipient_agent: str,
    ) -> WorkingMemoryContext:
        """Build context using only the current task's active entries."""

        if not isinstance(task_id, UUID):
            raise TypeError("task_id must be a UUID.")

        if (
            not isinstance(recipient_agent, str)
            or recipient_agent not in self.manager.policy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized working memory context recipient."
            )

        records = self.manager.search(
            requesting_agent="CoordinatorAgent",
            task_id=task_id,
            limit=self.MAX_CONTEXT_ITEMS,
        )

        selected = [
            WorkingMemoryContextItem(
                entry_id=record.entry_id,
                key=record.key,
                entry_type=record.entry_type,
                content=record.content,
                source_agent=record.source_agent,
            )
            for record in records[:self.MAX_CONTEXT_ITEMS]
        ]

        return WorkingMemoryContext(
            task_id=task_id,
            recipient_agent=recipient_agent,
            entries=selected,
        )
