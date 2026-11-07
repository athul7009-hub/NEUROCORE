
from datetime import datetime, timezone
from uuid import UUID

from app.memory.procedural_policy import ProceduralMemoryPolicy
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemoryStatus,
)
from app.memory.repositories.procedural_memory import (
    ProceduralMemoryRepository,
)
from app.memory.schemas import MemorySensitivity


class ProceduralMemoryManager:
    """Provides controlled access to procedural memory."""

    def __init__(
        self,
        repository: ProceduralMemoryRepository,
        policy: ProceduralMemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or ProceduralMemoryPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    def _authorize_requester(self, requesting_agent: str) -> None:
        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized procedural memory access."
            )

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_manage(requesting_agent):
            raise PermissionError(
                "Only the coordinator can manage procedural memories."
            )

    def remember(
        self,
        record: ProceduralMemoryRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores a new candidate procedural memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(record, ProceduralMemoryRecord):
            raise TypeError("Expected a ProceduralMemoryRecord.")

        if not self.policy.evaluate_storage(record):
            raise ValueError(
                "Procedural memory rejected by storage policy."
            )

        self.repository.save(record)

    def get(
        self,
        procedure_id: UUID,
        *,
        requesting_agent: str,
    ) -> ProceduralMemoryRecord | None:
        """Retrieves a validated procedural memory."""

        self._authorize_requester(requesting_agent)

        if not isinstance(procedure_id, UUID):
            raise TypeError("Procedure ID must be a UUID.")

        record = self.repository.get(procedure_id)

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
        name: str | None = None,
        sensitivity: MemorySensitivity | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ProceduralMemoryRecord]:
        """Searches validated procedures only."""

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
            name=name,
            status=ProceduralMemoryStatus.VALIDATED,
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
    ) -> list[ProceduralMemoryRecord]:
        """Returns unvalidated procedures for coordinator review."""

        self._authorize_coordinator(requesting_agent)

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        return self.repository.search(
            status=ProceduralMemoryStatus.CANDIDATE,
            limit=limit,
        )

    def validate(
        self,
        procedure_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Validates a candidate procedural memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(procedure_id, UUID):
            raise TypeError("Procedure ID must be a UUID.")

        record = self.repository.get(procedure_id)

        if (
            record is None
            or record.status != ProceduralMemoryStatus.CANDIDATE
        ):
            return False

        now = datetime.now(timezone.utc)

        validated_record = record.model_copy(
            update={
                "status": ProceduralMemoryStatus.VALIDATED,
                "validated_at": now,
                "validated_by": requesting_agent,
                "updated_at": now,
            }
        )

        return self.repository.update(validated_record)

    def deprecate(
        self,
        procedure_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Deprecates a candidate or validated procedure."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(procedure_id, UUID):
            raise TypeError("Procedure ID must be a UUID.")

        record = self.repository.get(procedure_id)

        if (
            record is None
            or record.status == ProceduralMemoryStatus.DEPRECATED
        ):
            return False

        now = datetime.now(timezone.utc)

        deprecated_record = record.model_copy(
            update={
                "status": ProceduralMemoryStatus.DEPRECATED,
                "validated_at": None,
                "validated_by": None,
                "updated_at": now,
            }
        )

        return self.repository.update(deprecated_record)
