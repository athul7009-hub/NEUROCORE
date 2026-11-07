
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
    ProceduralMemoryStatus,
)
from app.memory.schemas import MemorySensitivity


class ProceduralMemoryPolicy:
    """Controls procedural memory storage and retrieval."""

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
        record: ProceduralMemoryRecord,
    ) -> bool:
        """Checks whether a procedural memory can be stored."""

        if not isinstance(record, ProceduralMemoryRecord):
            return False

        return (
            record.sensitivity in self.ALLOWED_SENSITIVITIES
            and isinstance(record.source, ProceduralMemorySource)
            and record.status == ProceduralMemoryStatus.CANDIDATE
        )

    def evaluate_retrieval(
        self,
        record: ProceduralMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Allows trusted agents to retrieve validated procedures."""

        if not isinstance(record, ProceduralMemoryRecord):
            return False

        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.TRUSTED_AGENTS
        ):
            return False

        return (
            record.status == ProceduralMemoryStatus.VALIDATED
            and record.sensitivity in self.ALLOWED_SENSITIVITIES
        )

    def can_manage(self, requesting_agent: str) -> bool:
        """Only the coordinator can manage procedural memories."""

        return requesting_agent == "CoordinatorAgent"
