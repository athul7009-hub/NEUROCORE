
from uuid import UUID

from app.memory.memory_policy import MemoryPolicy
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.retention_policy import (
    MemoryRetentionPolicy,
    RetentionAssessment,
)
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)


class MemoryManager:
    """Provides a controlled interface to episodic memory."""

    def __init__(
        self,
        repository: EpisodicMemoryRepository,
        policy: MemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or MemoryPolicy()
        self.retention_policy = MemoryRetentionPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    def _authorize_requester(self, requesting_agent: str) -> None:
        """Ensures the requesting agent is trusted."""

        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError("Unauthorized memory retrieval.")

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        """Restricts memory lifecycle operations to the coordinator."""

        self._authorize_requester(requesting_agent)

        if requesting_agent != "CoordinatorAgent":
            raise PermissionError(
                "Only the coordinator can manage memory lifecycle operations."
            )

    def inspect_identity(
        self,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> MemoryLifecycleStatus | None:
        """Inspects episodic memory identity without exposing its content."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(task_id, UUID):
            raise TypeError("Task ID must be a UUID.")

        return self.repository.get_identity_status(task_id)

    def remember_task(
        self,
        record: EpisodicMemoryRecord,
        sensitivity: MemorySensitivity = MemorySensitivity.INTERNAL,
        source: MemorySource = MemorySource.COORDINATOR,
    ) -> None:
        """Stores a new active memory after policy validation."""

        if not isinstance(record, EpisodicMemoryRecord):
            raise TypeError("Expected an EpisodicMemoryRecord.")

        if (
            record.lifecycle_status != MemoryLifecycleStatus.ACTIVE
            or record.archived_at is not None
        ):
            raise ValueError("New memories must have an active lifecycle.")

        if not self.policy.evaluate(record, sensitivity, source):
            raise ValueError("Memory record rejected by storage policy.")

        approved_record = record.model_copy(
            update={
                "sensitivity": sensitivity,
                "source": source,
            }
        )

        self.repository.save(approved_record)

    def get_task(
        self,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> EpisodicMemoryRecord | None:
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

    def record_usage(
        self,
        task_ids: list[UUID],
        *,
        requesting_agent: str,
    ) -> None:
        """Records usage only for memories authorized for the agent."""

        self._authorize_requester(requesting_agent)

        if not isinstance(task_ids, list):
            raise TypeError("Task IDs must be provided as a list.")

        if any(not isinstance(task_id, UUID) for task_id in task_ids):
            raise TypeError("Every task ID must be a UUID.")

        for task_id in set(task_ids):
            record = self.repository.get(task_id)

            if (
                record is not None
                and self.policy.evaluate_retrieval(
                    record,
                    requesting_agent,
                )
            ):
                self.repository.record_usage(task_id)

    def assess_retention(
        self,
        *,
        requesting_agent: str,
        limit: int = 100,
    ) -> list[tuple[EpisodicMemoryRecord, RetentionAssessment]]:
        """Assesses active memories without changing them."""

        self._authorize_coordinator(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        records = self.repository.get_recent(limit=limit)

        return [
            (record, self.retention_policy.assess(record))
            for record in records
        ]

    def archive_task(
        self,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Archives an eligible memory through coordinator authorization."""

        self._authorize_coordinator(requesting_agent)

        record = self.repository.get(task_id)

        if record is None:
            return False

        assessment = self.retention_policy.assess(record)

        if not assessment.eligible:
            raise ValueError(
                "Memory is not eligible for archival: "
                + "; ".join(assessment.reasons)
            )

        return self.repository.archive(
            task_id,
            expected_record=record,
        )

    def restore_task(
        self,
        task_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Restores an archived memory through coordinator authorization."""

        self._authorize_coordinator(requesting_agent)

        return self.repository.restore(task_id)

    def get_archived_tasks(
        self,
        limit: int = 10,
        *,
        requesting_agent: str,
        intent: str | None = None,
    ) -> list[EpisodicMemoryRecord]:
        """Retrieves authorized archived memories for historical context."""

        self._authorize_requester(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        batch_size = 100
        offset = 0
        authorized_records = []

        while len(authorized_records) < limit:
            records = self.repository.get_archived(
                limit=batch_size,
                intent=intent,
                offset=offset,
            )

            if not records:
                break

            authorized_records.extend(
                record
                for record in records
                if self.policy.evaluate_archived_retrieval(
                    record,
                    requesting_agent,
                )
            )

            offset += len(records)

            if len(records) < batch_size:
                break

        return authorized_records[:limit]
