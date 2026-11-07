
from uuid import UUID

from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)
from app.memory.memory_policy import MemoryPolicy


class MemoryManager:
    """Provides a controlled interface to episodic memory."""

    def __init__(
        self,
        repository: EpisodicMemoryRepository,
        policy: MemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or MemoryPolicy()

    def initialize(self) -> None:
        """Initializes the memory storage."""

        self.repository.initialize()

    def remember_task(
        self,
        record: EpisodicMemoryRecord,
        sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL,
        source: MemorySource = MemorySource.COORDINATOR,
    ) -> None:
        """Stores a task memory if it satisfies the storage policy."""

        if not isinstance(record, EpisodicMemoryRecord):
            raise TypeError("Expected an EpisodicMemoryRecord.")

        if not self.policy.evaluate(record, sensitivity, source):
            raise ValueError("Memory record rejected by storage policy.")

        approved_record = record.model_copy(
            update={
                "sensitivity": sensitivity,
                "source": source,
            }
        )

        self.repository.save(approved_record)

    def _authorize_requester(self, requesting_agent: str) -> None:
        """Rejects agents that are not trusted to retrieve memory."""

        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError("Unauthorized memory retrieval.")

    def get_task(
        self,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> EpisodicMemoryRecord | None:
        """Retrieves a task memory after authorization."""

        self._authorize_requester(requesting_agent)

        record = self.repository.get(task_id)

        if record is None:
            return None

        if not self.policy.evaluate_retrieval(record, requesting_agent):
            return None

        return record

    def get_recent_tasks(
        self,
        limit: int = 10,
        *,
        requesting_agent: str,
        intent: str | None = None,
        status: MemoryStatus | None = None,
        agent_name: str | None = None,
    ) -> list[EpisodicMemoryRecord]:
        """Retrieves the requested number of authorized recent memories."""

        self._authorize_requester(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        batch_size = 100
        offset = 0
        authorized_records = []

        while len(authorized_records) < limit:
            records = self.repository.get_recent(
                limit=batch_size,
                intent=intent,
                status=status,
                agent_name=agent_name,
                offset=offset,
            )

            if not records:
                break

            authorized_records.extend(
                record
                for record in records
                if self.policy.evaluate_retrieval(
                    record,
                    requesting_agent,
                )
            )

            offset += len(records)

            if len(records) < batch_size:
                break

        return authorized_records[:limit]
