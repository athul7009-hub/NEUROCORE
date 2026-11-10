
from datetime import datetime, timezone
from uuid import UUID

from app.memory.meta_conflict_policy import MetaMemoryConflictPolicy
from app.memory.meta_conflict_schemas import (
    MetaMemoryConflictRecord,
    MetaMemoryConflictStatus,
    MetaMemoryConflictType,
)
from app.memory.repositories.meta_conflict import (
    MetaMemoryConflictRepository,
)


class MetaMemoryConflictManager:
    """Provides controlled access to meta-memory conflicts."""

    def __init__(
        self,
        repository: MetaMemoryConflictRepository,
        policy: MetaMemoryConflictPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or MetaMemoryConflictPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    @staticmethod
    def _current_time() -> datetime:
        return datetime.now(timezone.utc)

    def _authorize_requester(self, requesting_agent: str) -> None:
        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError("Unauthorized conflict access.")

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_review(requesting_agent):
            raise PermissionError(
                "Only the coordinator can review memory conflicts."
            )

    def remember(
        self,
        record: MetaMemoryConflictRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores a detected memory conflict."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(record, MetaMemoryConflictRecord):
            raise TypeError("Expected a MetaMemoryConflictRecord.")

        if record.status != MetaMemoryConflictStatus.DETECTED:
            raise ValueError("New conflicts must have DETECTED status.")

        if not self.policy.evaluate_storage(record):
            raise ValueError("Conflict rejected by storage policy.")

        self.repository.save(record)

    def get(
        self,
        conflict_id: UUID,
        *,
        requesting_agent: str,
    ) -> MetaMemoryConflictRecord | None:
        """Retrieves an authorized conflict."""

        self._authorize_requester(requesting_agent)

        if not isinstance(conflict_id, UUID):
            raise TypeError("Conflict ID must be a UUID.")

        record = self.repository.get(conflict_id)

        if record is None:
            return None

        if not self.policy.evaluate_retrieval(
            record,
            requesting_agent,
        ):
            return None

        return record

    def search(
        self,
        *,
        requesting_agent: str,
        status: MetaMemoryConflictStatus | None = None,
        conflict_type: MetaMemoryConflictType | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MetaMemoryConflictRecord]:
        """Searches conflicts and applies retrieval authorization."""

        self._authorize_requester(requesting_agent)

        records = self.repository.search(
            status=status,
            conflict_type=conflict_type,
            limit=limit,
            offset=offset,
        )

        return [
            record
            for record in records
            if self.policy.evaluate_retrieval(
                record,
                requesting_agent,
            )
        ]

    def _transition(
        self,
        conflict_id: UUID,
        *,
        requesting_agent: str,
        expected_status: MetaMemoryConflictStatus,
        new_status: MetaMemoryConflictStatus,
    ) -> bool:
        self._authorize_coordinator(requesting_agent)

        if not isinstance(conflict_id, UUID):
            raise TypeError("Conflict ID must be a UUID.")

        now = self._current_time()

        return self.repository.transition_status(
            conflict_id,
            expected_status=expected_status,
            new_status=new_status,
            reviewed_at=now,
        )



    def confirm(
        self,
        conflict_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Confirms a detected conflict."""

        return self._transition(
            conflict_id,
            requesting_agent=requesting_agent,
            expected_status=MetaMemoryConflictStatus.DETECTED,
            new_status=MetaMemoryConflictStatus.CONFIRMED,
        )

    def dismiss(
        self,
        conflict_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Dismisses a detected conflict."""

        return self._transition(
            conflict_id,
            requesting_agent=requesting_agent,
            expected_status=MetaMemoryConflictStatus.DETECTED,
            new_status=MetaMemoryConflictStatus.DISMISSED,
        )

    def resolve(
        self,
        conflict_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Marks a confirmed conflict as resolved."""

        return self._transition(
            conflict_id,
            requesting_agent=requesting_agent,
            expected_status=MetaMemoryConflictStatus.CONFIRMED,
            new_status=MetaMemoryConflictStatus.RESOLVED,
        )
