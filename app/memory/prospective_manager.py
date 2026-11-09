
from datetime import datetime, timezone
from uuid import UUID

from app.memory.prospective_policy import ProspectiveMemoryPolicy
from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)
from app.memory.repositories.prospective_memory import (
    ProspectiveMemoryRepository,
)
from app.memory.schemas import MemorySensitivity
from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
)

class ProspectiveMemoryManager:
    """Provides controlled access to prospective memory."""

    def __init__(
        self,
        repository: ProspectiveMemoryRepository,
        policy: ProspectiveMemoryPolicy | None = None,
    ):
        self.repository = repository
        self.policy = policy or ProspectiveMemoryPolicy()

    def initialize(self) -> None:
        self.repository.initialize()

    def _authorize_requester(self, requesting_agent: str) -> None:
        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.policy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized prospective memory access."
            )

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_manage(requesting_agent):
            raise PermissionError(
                "Only the coordinator can manage prospective memories."
            )

    @staticmethod
    def _validate_memory_id(memory_id: UUID) -> None:
        if not isinstance(memory_id, UUID):
            raise TypeError("Memory ID must be a UUID.")

    @staticmethod
    def _current_time() -> datetime:
        return datetime.now(timezone.utc)

    def remember(
        self,
        record: ProspectiveMemoryRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores a new pending prospective memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(record, ProspectiveMemoryRecord):
            raise TypeError("Expected a ProspectiveMemoryRecord.")

        if not self.policy.evaluate_storage(record):
            raise ValueError(
                "Prospective memory rejected by storage policy."
            )

        self.repository.save(record)

    def get(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> ProspectiveMemoryRecord | None:
        """Retrieves an authorized active intention."""

        self._authorize_requester(requesting_agent)
        self._validate_memory_id(memory_id)

        record = self.repository.get(memory_id)

        if record is None:
            return None

        if not self.policy.evaluate_retrieval(
            record,
            requesting_agent,
        ):
            return None

        return record
    def inspect_identity(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> MemoryIdentityAssessment:
        """Inspects prospective memory identity without retrieving content."""

        self._authorize_coordinator(requesting_agent)
        self._validate_memory_id(memory_id)

        status = self.repository.get_identity_status(memory_id)

        if status is None:
            return MemoryIdentityAssessment(
                memory_type="prospective",
                memory_id=memory_id,
                exists=False,
                lifecycle_status=None,
                availability=MemoryIdentityAvailability.NOT_FOUND,
            )

        availability = (
            MemoryIdentityAvailability.AVAILABLE
            if status in {
                ProspectiveMemoryStatus.PENDING,
                ProspectiveMemoryStatus.TRIGGERED,
            }
            else MemoryIdentityAvailability.INACTIVE
        )

        return MemoryIdentityAssessment(
            memory_type="prospective",
            memory_id=memory_id,
            exists=True,
            lifecycle_status=status.value,
            availability=availability,
        )
    def search(
        self,
        *,
        requesting_agent: str,
        title: str | None = None,
        status: ProspectiveMemoryStatus | None = None,
        trigger_type: ProspectiveTriggerType | None = None,
        priority: ProspectiveMemoryPriority | None = None,
        sensitivity: MemorySensitivity | None = None,
        source: ProspectiveMemorySource | None = None,
        source_agent: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ProspectiveMemoryRecord]:
        """Searches prospective memories and filters unauthorized records."""

        self._authorize_requester(requesting_agent)

        records = self.repository.search(
            title=title,
            status=status,
            trigger_type=trigger_type,
            priority=priority,
            sensitivity=sensitivity,
            source=source,
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
            )
        ]

    def get_due(
        self,
        *,
        requesting_agent: str,
        now: datetime | None = None,
        limit: int = 10,
    ) -> list[ProspectiveMemoryRecord]:
        """Retrieves due time-based intentions without changing their status."""

        self._authorize_requester(requesting_agent)

        records = self.repository.get_due(
            now=now,
            limit=limit,
        )

        return [
            record
            for record in records
            if self.policy.evaluate_retrieval(
                record,
                requesting_agent,
            )
        ]

    def trigger(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Marks an eligible, unprotected pending intention as triggered."""

        self._authorize_coordinator(requesting_agent)
        self._validate_memory_id(memory_id)

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.is_protected
            or record.status != ProspectiveMemoryStatus.PENDING
        ):
            return False

        now = self._current_time()

        if record.expires_at is not None and record.expires_at <= now:
            return False

        if (
            record.trigger_type == ProspectiveTriggerType.TIME
            and (record.due_at is None or record.due_at > now)
        ):
            return False

        updated = record.model_copy(
            update={
                "status": ProspectiveMemoryStatus.TRIGGERED,
                "triggered_at": now,
                "updated_at": now,
            }
        )

        return self.repository.update(
            updated,
            expected_status=ProspectiveMemoryStatus.PENDING,
        )

    def complete(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Completes an unprotected triggered intention."""

        self._authorize_coordinator(requesting_agent)
        self._validate_memory_id(memory_id)

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.is_protected
            or record.status != ProspectiveMemoryStatus.TRIGGERED
        ):
            return False

        now = self._current_time()

        updated = record.model_copy(
            update={
                "status": ProspectiveMemoryStatus.COMPLETED,
                "completed_at": now,
                "updated_at": now,
            }
        )

        return self.repository.update(
            updated,
            expected_status=ProspectiveMemoryStatus.TRIGGERED,
        )

    def cancel(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Cancels an unprotected pending intention."""

        self._authorize_coordinator(requesting_agent)
        self._validate_memory_id(memory_id)

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.is_protected
            or record.status != ProspectiveMemoryStatus.PENDING
        ):
            return False

        updated = record.model_copy(
            update={
                "status": ProspectiveMemoryStatus.CANCELLED,
                "updated_at": self._current_time(),
            }
        )

        return self.repository.update(
            updated,
            expected_status=ProspectiveMemoryStatus.PENDING,
        )

    def expire(
        self,
        memory_id: UUID,
        *,
        requesting_agent: str,
    ) -> bool:
        """Expires an unprotected pending intention past its expiration time."""

        self._authorize_coordinator(requesting_agent)
        self._validate_memory_id(memory_id)

        record = self.repository.get(memory_id)

        if (
            record is None
            or record.is_protected
            or record.status != ProspectiveMemoryStatus.PENDING
            or record.expires_at is None
        ):
            return False

        now = self._current_time()

        if record.expires_at > now:
            return False

        updated = record.model_copy(
            update={
                "status": ProspectiveMemoryStatus.EXPIRED,
                "updated_at": now,
            }
        )

        return self.repository.update(
            updated,
            expected_status=ProspectiveMemoryStatus.PENDING,
        )
