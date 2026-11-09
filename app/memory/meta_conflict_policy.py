from app.memory.meta_conflict_schemas import MetaMemoryConflictRecord
from app.memory.meta_schemas import MetaMemoryType


class MetaMemoryConflictPolicy:
    """Controls meta-memory conflict storage, retrieval, and review."""

    TRUSTED_AGENTS = frozenset({
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    })

    ALLOWED_MEMORY_TYPES = frozenset(MetaMemoryType)

    def evaluate_storage(self, record: MetaMemoryConflictRecord) -> bool:
        """Checks whether a conflict record can be stored."""

        if not isinstance(record, MetaMemoryConflictRecord):
            return False

        return (
            record.memory_type_a in self.ALLOWED_MEMORY_TYPES
            and record.memory_type_b in self.ALLOWED_MEMORY_TYPES
        )

    def evaluate_retrieval(
        self,
        record: MetaMemoryConflictRecord,
        requesting_agent: str,
    ) -> bool:
        """Allows trusted agents to retrieve conflict records."""

        if not isinstance(record, MetaMemoryConflictRecord):
            return False

        return (
            isinstance(requesting_agent, str)
            and requesting_agent in self.TRUSTED_AGENTS
            and record.memory_type_a in self.ALLOWED_MEMORY_TYPES
            and record.memory_type_b in self.ALLOWED_MEMORY_TYPES
        )

    def can_review(self, requesting_agent: str) -> bool:
        """Only CoordinatorAgent can review conflicts."""

        return requesting_agent == "CoordinatorAgent"