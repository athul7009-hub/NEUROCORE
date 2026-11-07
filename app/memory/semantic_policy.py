from app.memory.schemas import MemorySensitivity
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


class SemanticMemoryPolicy:
    """Controls semantic memory storage and retrieval."""

    ALLOWED_SENSITIVITIES = {
        MemorySensitivity.PUBLIC,
        MemorySensitivity.INTERNAL,
    }

    TRUSTED_AGENTS = frozenset({
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    })

    def evaluate_storage(
        self,
        record: SemanticMemoryRecord,
    ) -> bool:
        """Checks whether a semantic memory can be stored."""

        if not isinstance(record, SemanticMemoryRecord):
            return False

        return (
            record.sensitivity in self.ALLOWED_SENSITIVITIES
            and isinstance(record.source, SemanticMemorySource)
            and record.status == SemanticMemoryStatus.CANDIDATE
        )

    def evaluate_retrieval(
        self,
        record: SemanticMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Allows trusted agents to retrieve validated memories."""

        if not isinstance(record, SemanticMemoryRecord):
            return False

        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.TRUSTED_AGENTS
        ):
            return False

        return (
            record.status == SemanticMemoryStatus.VALIDATED
            and record.sensitivity in self.ALLOWED_SENSITIVITIES
        )

    def can_manage(self, requesting_agent: str) -> bool:
        """Only the coordinator can validate or deprecate memories."""

        return requesting_agent == "CoordinatorAgent"