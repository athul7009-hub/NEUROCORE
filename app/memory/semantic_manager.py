from datetime import datetime, timezone
from uuid import UUID

from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.schemas import MemorySensitivity
from app.memory.semantic_policy import SemanticMemoryPolicy
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemoryStatus,
)


class SemanticMemoryManager:
    """Provides controlled access to semantic memory."""

    def __init__(
        self,
        repository: SemanticMemoryRepository,
        policy: SemanticMemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or SemanticMemoryPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    def _authorize_requester(self, requesting_agent: str) -> None:
        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized semantic memory access."
            )

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_manage(requesting_agent):
            raise PermissionError(
                "Only the coordinator can manage semantic memories."
            )
    def inspect_identity(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> SemanticMemoryStatus | None:
        """Inspects semantic memory identity without exposing its content."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(memory_id, UUID):
            raise TypeError("Memory ID must be a UUID.")

        return self.repository.get_identity_status(memory_id)
    def remember(
        self,
        record: SemanticMemoryRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores a new candidate semantic memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(record, SemanticMemoryRecord):
            raise TypeError("Expected a SemanticMemoryRecord.")

        if not self.policy.evaluate_storage(record):
            raise ValueError(
                "Semantic memory rejected by storage policy."
            )

        self.repository.save(record)

    def get(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> SemanticMemoryRecord | None:
        """Retrieves a validated semantic memory."""

        self._authorize_requester(requesting_agent)

        if not isinstance(memory_id, UUID):
            raise TypeError("Memory ID must be a UUID.")

        record = self.repository.get(memory_id)

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
        subject: str | None = None,
        predicate: str | None = None,
        sensitivity: MemorySensitivity | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[SemanticMemoryRecord]:
        """Searches validated semantic memories only."""

        self._authorize_requester(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        records = self.repository.search(
            subject=subject,
            predicate=predicate,
            status=SemanticMemoryStatus.VALIDATED,
            sensitivity=sensitivity,
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

    def get_candidates(
        self,
        *,
        requesting_agent: str,
        limit: int = 50,
    ) -> list[SemanticMemoryRecord]:
        """Returns unvalidated candidates for coordinator review."""

        self._authorize_coordinator(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        return self.repository.search(
            status=SemanticMemoryStatus.CANDIDATE,
            limit=limit,
        )

    def validate(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Validates a candidate semantic memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(memory_id, UUID):
            raise TypeError("Memory ID must be a UUID.")

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.status != SemanticMemoryStatus.CANDIDATE
        ):
            return False

        validated_record = record.model_copy(
            update={
                "status": SemanticMemoryStatus.VALIDATED,
                "validated_at": datetime.now(timezone.utc),
                "validated_by": requesting_agent,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return self.repository.update(validated_record)

    def deprecate(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Deprecates a candidate or validated semantic memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(memory_id, UUID):
            raise TypeError("Memory ID must be a UUID.")

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.status == SemanticMemoryStatus.DEPRECATED
        ):
            return False

        deprecated_record = record.model_copy(
            update={
                "status": SemanticMemoryStatus.DEPRECATED,
                "validated_at": None,
                "validated_by": None,
                "updated_at": datetime.now(timezone.utc),
            }
        )

        return self.repository.update(deprecated_record)