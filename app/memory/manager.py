
from uuid import UUID

from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.schemas import EpisodicMemoryRecord


class MemoryManager:
    """Provides a controlled interface for episodic memory."""

    def __init__(self, repository: EpisodicMemoryRepository):
        self.repository = repository

    def initialize(self) -> None:
        """Initializes the memory storage."""
        self.repository.initialize()

    def remember_task(self, record: EpisodicMemoryRecord) -> None:
        """Stores a validated task memory."""
        if not isinstance(record, EpisodicMemoryRecord):
            raise TypeError("Expected an EpisodicMemoryRecord.")

        self.repository.save(record)

    def get_task(self, task_id: UUID) -> EpisodicMemoryRecord | None:
        """Retrieves a task memory."""
        return self.repository.get(task_id)

    def get_recent_tasks(
        self,
        limit: int = 10,
    ) -> list[EpisodicMemoryRecord]:
        """Retrieves recent task memories."""
        return self.repository.get_recent(limit)
