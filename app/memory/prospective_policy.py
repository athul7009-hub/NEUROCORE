
from app.memory.prospective_schemas import (
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
)
from app.memory.schemas import MemorySensitivity


class ProspectiveMemoryPolicy:
    """Controls prospective memory storage, retrieval, and management."""

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

    RETRIEVABLE_STATUSES = {
        ProspectiveMemoryStatus.PENDING,
        ProspectiveMemoryStatus.TRIGGERED,
    }

    def evaluate_storage(
        self,
        record: ProspectiveMemoryRecord,
    ) -> bool:
        """Checks whether a prospective memory can be stored."""

        if not isinstance(record, ProspectiveMemoryRecord):
            return False

        return (
            record.sensitivity in self.ALLOWED_SENSITIVITIES
            and isinstance(record.source, ProspectiveMemorySource)
            and record.source_agent in self.TRUSTED_AGENTS
            and record.status == ProspectiveMemoryStatus.PENDING
        )

    def evaluate_retrieval(
        self,
        record: ProspectiveMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Allows trusted agents to retrieve active intentions."""

        if not isinstance(record, ProspectiveMemoryRecord):
            return False

        if (
            not isinstance(requesting_agent, str)
            or not requesting_agent.strip()
            or requesting_agent not in self.TRUSTED_AGENTS
        ):
            return False

        return (
            record.status in self.RETRIEVABLE_STATUSES
            and record.sensitivity in self.ALLOWED_SENSITIVITIES
        )

    def can_manage(self, requesting_agent: str) -> bool:
        """Only the coordinator can manage prospective memories."""

        return requesting_agent == "CoordinatorAgent"
