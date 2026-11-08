from datetime import datetime, timezone
from uuid import UUID
from app.memory.schemas import MemorySensitivity
from app.memory.working_schemas import WorkingMemoryRecord


class WorkingMemoryPolicy:
    """Controls task-scoped working memory access."""

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
        record: WorkingMemoryRecord,
        requesting_agent: str,
    ) -> bool:
        """Checks whether an agent can store a working memory entry."""

        if not isinstance(record, WorkingMemoryRecord):
            return False

        if not self.is_trusted(requesting_agent):
            return False

        return (
            record.source_agent == requesting_agent
            and record.sensitivity in self.ALLOWED_SENSITIVITIES
            and record.expires_at > datetime.now(timezone.utc)
        )

    def evaluate_retrieval(
        self,
        record: WorkingMemoryRecord,
        requesting_agent: str,
        task_id,
    ) -> bool:
        """Checks trusted-agent access within the owning task."""

        if not isinstance(record, WorkingMemoryRecord):
            return False

        if not self.is_trusted(requesting_agent):
            return False

        if not isinstance(task_id, UUID):
            return False

        return (
            record.task_id == task_id
            and record.sensitivity in self.ALLOWED_SENSITIVITIES
            and record.expires_at > datetime.now(timezone.utc)
        )

    def can_manage(self, requesting_agent: str) -> bool:
        """Only the coordinator can perform lifecycle management."""

        return requesting_agent == "CoordinatorAgent"

    @classmethod
    def is_trusted(cls, requesting_agent: str) -> bool:
        """Checks whether the requesting agent is trusted."""

        return (
            isinstance(requesting_agent, str)
            and bool(requesting_agent.strip())
            and requesting_agent in cls.TRUSTED_AGENTS
        )