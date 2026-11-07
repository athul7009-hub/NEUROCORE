
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemorySensitivity,
    MemoryLifecycleStatus,
    MemorySource,
)


class MemoryPolicy:
    """Controls episodic memory storage and retrieval."""

    ALLOWED_SENSITIVITIES = {
        MemorySensitivity.PUBLIC,
        MemorySensitivity.INTERNAL,
    }

    ALLOWED_SOURCES = {
        MemorySource.COORDINATOR,
        MemorySource.SYSTEM,
    }

    TRUSTED_AGENTS = frozenset({
        "CoordinatorAgent",
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    })

    def evaluate(
        self,
        record: EpisodicMemoryRecord,
        sensitivity: MemorySensitivity,
        source: MemorySource,
    ) -> bool:
        """Returns whether a memory satisfies the storage policy."""

        if not isinstance(record, EpisodicMemoryRecord):
            return False

        if not isinstance(sensitivity, MemorySensitivity):
            return False

        if not isinstance(source, MemorySource):
            return False

        return (
            sensitivity in self.ALLOWED_SENSITIVITIES
            and source in self.ALLOWED_SOURCES
        )

    def evaluate_retrieval(
        self,
        record: EpisodicMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Checks whether an agent can retrieve a memory."""

        if not isinstance(record, EpisodicMemoryRecord):
            return False

        if not isinstance(requesting_agent, str):
            return False

        if not requesting_agent.strip():
            return False

        if requesting_agent not in self.TRUSTED_AGENTS:
            return False

        return record.sensitivity in {
            MemorySensitivity.PUBLIC,
            MemorySensitivity.INTERNAL,
        }
    def evaluate_archived_retrieval(
        self,
        record: EpisodicMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Authorizes historical retrieval without changing record state."""

        if not isinstance(record, EpisodicMemoryRecord):
            return False

        if (
            not isinstance(requesting_agent, str)
            or requesting_agent not in self.TRUSTED_AGENTS
        ):
            return False

        if record.lifecycle_status != MemoryLifecycleStatus.ARCHIVED:
            return False

        return record.sensitivity in {
            MemorySensitivity.PUBLIC,
            MemorySensitivity.INTERNAL,
        }