from uuid import UUID

from app.memory.repositories.working_memory import (
    WorkingMemoryRepository,
)
from app.memory.working_policy import WorkingMemoryPolicy
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


class WorkingMemoryManager:
    """Provides controlled access to task-scoped working memory."""

    def __init__(
        self,
        repository: WorkingMemoryRepository,
        policy: WorkingMemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or WorkingMemoryPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    def _authorize_requester(self, requesting_agent: str) -> None:
        if not self.policy.is_trusted(requesting_agent):
            raise PermissionError(
                "Unauthorized working memory access."
            )

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_manage(requesting_agent):
            raise PermissionError(
                "Only the coordinator can manage working memory."
            )

    @staticmethod
    def _validate_task_id(task_id: UUID) -> None:
        if not isinstance(task_id, UUID):
            raise TypeError("Task ID must be a UUID.")

    @staticmethod
    def _validate_entry_id(entry_id: UUID) -> None:
        if not isinstance(entry_id, UUID):
            raise TypeError("Entry ID must be a UUID.")

    def remember(
        self,
        record: WorkingMemoryRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores a task-scoped working memory entry."""

        self._authorize_requester(requesting_agent)

        if not isinstance(record, WorkingMemoryRecord):
            raise TypeError("Expected a WorkingMemoryRecord.")

        if not self.policy.evaluate_storage(
            record,
            requesting_agent,
        ):
            raise ValueError(
                "Working memory rejected by storage policy."
            )

        self.repository.save(record)

    def get(
        self,
        entry_id: UUID,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> WorkingMemoryRecord | None:
        """Retrieves an entry belonging to the specified task."""

        self._authorize_requester(requesting_agent)
        self._validate_entry_id(entry_id)
        self._validate_task_id(task_id)

        record = self.repository.get(entry_id, task_id)

        if record is None:
            return None

        if not self.policy.evaluate_retrieval(
            record,
            requesting_agent,
            task_id,
        ):
            return None

        return record

    def search(
        self,
        *,
        task_id: UUID,
        requesting_agent: str,
        entry_type: WorkingMemoryEntryType | None = None,
        source_agent: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WorkingMemoryRecord]:
        """Searches unexpired entries within one task."""

        self._authorize_requester(requesting_agent)
        self._validate_task_id(task_id)

        if entry_type is not None and not isinstance(
            entry_type,
            WorkingMemoryEntryType,
        ):
            raise TypeError("Invalid working memory entry type.")

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        records = self.repository.search(
            task_id=task_id,
            entry_type=entry_type,
            source_agent=source_agent,
            limit=limit,
            offset=offset,
        )

        return [
            record
            for record in records
            if self.policy.evaluate_retrieval(
                record,
                requesting_agent,
                task_id,
            )
        ]

    def update(
        self,
        record: WorkingMemoryRecord,
        *,
        requesting_agent: str,
    ) -> bool:
        """Updates an existing, unexpired entry owned by the agent."""

        self._authorize_requester(requesting_agent)

        if not isinstance(record, WorkingMemoryRecord):
            raise TypeError("Expected a WorkingMemoryRecord.")

        if not self.policy.evaluate_storage(
            record,
            requesting_agent,
        ):
            raise ValueError(
                "Working memory update rejected by policy."
            )

        existing = self.repository.get(
            record.entry_id,
            record.task_id,
        )

        if existing is None:
            return False

        if existing.source_agent != requesting_agent:
            raise PermissionError(
                "An agent cannot update another agent's entry."
            )

        return self.repository.update(record)

    def cleanup_expired(
        self,
        *,
        requesting_agent: str,
    ) -> int:
        """Deletes expired entries. Coordinator-only operation."""

        self._authorize_coordinator(requesting_agent)

        return self.repository.delete_expired()