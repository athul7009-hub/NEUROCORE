
import sqlite3
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.schemas import EpisodicMemoryRecord


class EpisodicMemoryRepository:
    """Stores and retrieves completed or failed task history."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the episodic memory table if it doesn't exist."""
        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS episodic_memory (
                    task_id TEXT PRIMARY KEY,
                    intent TEXT NOT NULL,
                    status TEXT NOT NULL,
                    agent_name TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL
                )
                """
            )

    def save(self, record: EpisodicMemoryRecord) -> None:
        """Persists one episodic memory record."""
        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO episodic_memory (
                    task_id,
                    intent,
                    status,
                    agent_name,
                    summary,
                    created_at,
                    completed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.task_id),
                    record.intent,
                    record.status.value,
                    record.agent_name,
                    record.summary,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat(),
                ),
            )

    def get(self, task_id: UUID) -> EpisodicMemoryRecord | None:
        """Retrieves one memory record by task ID."""
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT * FROM episodic_memory WHERE task_id = ?",
                (str(task_id),),
            ).fetchone()

        if row is None:
            return None

        return EpisodicMemoryRecord(
            task_id=row["task_id"],
            intent=row["intent"],
            status=row["status"],
            agent_name=row["agent_name"],
            summary=row["summary"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
        )

    def get_recent(self, limit: int = 10) -> list[EpisodicMemoryRecord]:
        """Retrieves the most recent task records."""
        if limit < 1:
            raise ValueError("Limit must be positive.")

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM episodic_memory
                ORDER BY completed_at DESC, rowid DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            EpisodicMemoryRecord(
                task_id=row["task_id"],
                intent=row["intent"],
                status=row["status"],
                agent_name=row["agent_name"],
                summary=row["summary"],
                created_at=row["created_at"],
                completed_at=row["completed_at"],
            )
            for row in rows
        ]
