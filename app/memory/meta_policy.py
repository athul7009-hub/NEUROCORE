
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryType,
)


class MetaMemoryPolicy:
    """Controls meta-memory storage, retrieval, and management."""

    TRUSTED_AGENTS = frozenset({
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    })

    ALLOWED_MEMORY_TYPES = frozenset(MetaMemoryType)

    def evaluate_storage(self, record: MetaMemoryRecord) -> bool:
        """Checks whether metadata can be stored."""

        if not isinstance(record, MetaMemoryRecord):
            return False

        return record.memory_type in self.ALLOWED_MEMORY_TYPES

    def evaluate_retrieval(
        self,
        record: MetaMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Allows trusted agents to retrieve metadata."""

        if not isinstance(record, MetaMemoryRecord):
            return False

        return (
            isinstance(requesting_agent, str)
            and requesting_agent in self.TRUSTED_AGENTS
            and record.memory_type in self.ALLOWED_MEMORY_TYPES
        )

    def can_manage(self, requesting_agent: str) -> bool:
        """Only CoordinatorAgent can manage assessments."""

        return requesting_agent == "CoordinatorAgent"

    def can_record_usage(self, requesting_agent: str) -> bool:
        """Trusted agents can record their memory retrieval usage."""

        return (
            isinstance(requesting_agent, str)
            and requesting_agent in self.TRUSTED_AGENTS
        )
