
from datetime import datetime, timezone
from uuid import UUID

from app.memory.meta_assessment import MetaMemoryAssessmentEngine
from app.memory.meta_assessment_schemas import MetaMemoryAssessment
from app.memory.meta_policy import MetaMemoryPolicy
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)
from app.memory.repositories.meta_memory import MetaMemoryRepository


class MetaMemoryManager:
    """Provides controlled access to meta-memory."""

    def __init__(
        self,
        repository: MetaMemoryRepository,
        policy: MetaMemoryPolicy | None = None,
        assessment_engine: MetaMemoryAssessmentEngine | None = None,
    ):
        self.repository = repository
        self.policy = policy or MetaMemoryPolicy()
        self.assessment_engine = (
            assessment_engine or MetaMemoryAssessmentEngine()
        )

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
            raise PermissionError("Unauthorized meta-memory access.")

    def _authorize_coordinator(self, requesting_agent: str) -> None:
        self._authorize_requester(requesting_agent)

        if not self.policy.can_manage(requesting_agent):
            raise PermissionError(
                "Only the coordinator can manage meta-memory assessments."
            )
    def authorize_maintenance(self, requesting_agent: str) -> None:
        """Authorizes an agent to perform meta-memory maintenance."""
        self._authorize_coordinator(requesting_agent)
    def remember(
        self,
        record: MetaMemoryRecord,
        *,
        requesting_agent: str,
    ) -> None:
        """Stores metadata about an existing memory."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("Expected a MetaMemoryRecord.")

        if not self.policy.evaluate_storage(record):
            raise ValueError("Meta-memory rejected by storage policy.")

        self.repository.save(record)

    def get(
        self,
        meta_id: UUID,
        *,
        requesting_agent: str,
    ) -> MetaMemoryRecord | None:
        """Retrieves authorized metadata by its ID."""

        self._authorize_requester(requesting_agent)

        if not isinstance(meta_id, UUID):
            raise TypeError("Meta-memory ID must be a UUID.")

        record = self.repository.get(meta_id)

        if record is None:
            return None

        if not self.policy.evaluate_retrieval(
            record,
            requesting_agent,
        ):
            return None

        return record

    def get_for_memory(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
        *,
        requesting_agent: str,
    ) -> MetaMemoryRecord | None:
        """Retrieves metadata using the original memory identity."""

        self._authorize_requester(requesting_agent)

        record = self.repository.get_for_memory(
            memory_type,
            memory_id,
        )

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
        memory_type: MetaMemoryType | None = None,
        staleness_status: MetaMemoryStalenessStatus | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MetaMemoryRecord]:
        """Searches metadata and applies retrieval authorization."""

        self._authorize_requester(requesting_agent)

        records = self.repository.search(
            memory_type=memory_type,
            staleness_status=staleness_status,
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

    def assess(
        self,
        meta_id: UUID,
        *,
        requesting_agent: str,
        now: datetime | None = None,
    ) -> MetaMemoryAssessment | None:
        """Returns an advisory assessment without persisting changes."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(meta_id, UUID):
            raise TypeError("Meta-memory ID must be a UUID.")

        record = self.repository.get(meta_id)

        if record is None:
            return None

        return self.assessment_engine.assess(
            record,
            now=now,
        )
    def assess_and_persist(
        self,
        meta_id: UUID,
        *,
        requesting_agent: str,
        now: datetime | None = None,
    ) -> MetaMemoryAssessment | None:
        """Assesses metadata and persists the generated assessment."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(meta_id, UUID):
            raise TypeError("Meta-memory ID must be a UUID.")

        record = self.repository.get(meta_id)

        if record is None:
            return None

        assessment = self.assessment_engine.assess(
            record,
            now=now,
        )

        updated = self.repository.update_assessment(
            meta_id,
            quality_score=assessment.quality_score,
            assessment_confidence=assessment.assessment_confidence,
            staleness_status=assessment.staleness_status,
            assessed_at=assessment.assessed_at,
        )

        if not updated:
            return None

        return assessment
   
    def update_assessment(
        self,
        meta_id: UUID,
        *,
        requesting_agent: str,
        quality_score: float | None,
        assessment_confidence: float,
        staleness_status: MetaMemoryStalenessStatus,
    ) -> bool:
        """Persists assessment without overwriting concurrent usage updates."""

        self._authorize_coordinator(requesting_agent)

        if not isinstance(meta_id, UUID):
            raise TypeError("Meta-memory ID must be a UUID.")
        if quality_score is not None:
            if (
                isinstance(quality_score, bool)
                or not isinstance(quality_score, (int, float))
                or not 0 <= quality_score <= 1
            ):
                raise ValueError(
                    "quality_score must be between 0 and 1."
                )

        if (
            isinstance(assessment_confidence, bool)
            or not isinstance(assessment_confidence, (int, float))
            or not 0 <= assessment_confidence <= 1
        ):
            raise ValueError(
                "assessment_confidence must be between 0 and 1."
            )
        if not isinstance(
            staleness_status,
            MetaMemoryStalenessStatus,
        ):
            raise TypeError("Invalid staleness status.")

        now = self._current_time()

        return self.repository.update_assessment(
            meta_id,
            quality_score=quality_score,
            assessment_confidence=assessment_confidence,
            staleness_status=staleness_status,
            assessed_at=now,
        )


    def record_usage(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
        *,
        requesting_agent: str,
        retrieved_at: datetime | None = None,
    ) -> bool:
        """Records a trusted agent's retrieval of an existing memory."""

        self._authorize_requester(requesting_agent)

        if not self.policy.can_record_usage(requesting_agent):
            raise PermissionError(
                "Agent is not authorized to record memory usage."
            )

        return self.repository.record_usage(
            memory_type,
            memory_id,
            retrieved_at=retrieved_at,
        )
