
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)


class EpisodicMemoryRepository:
    """Stores and retrieves completed or failed task history."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates or safely migrates the episodic memory table."""

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
                    completed_at TEXT NOT NULL,
                    sensitivity TEXT NOT NULL
                        DEFAULT 'legacy_unclassified',
                    source TEXT NOT NULL DEFAULT 'legacy'
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(episodic_memory)"
                ).fetchall()
            }

            migrations = {
                "sensitivity": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN sensitivity TEXT NOT NULL "
                    "DEFAULT 'legacy_unclassified'"
                ),
                "source": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN source TEXT NOT NULL "
                    "DEFAULT 'legacy'"
                ),
            }

            for column, migration_sql in migrations.items():
                if column not in columns:
                    connection.execute(migration_sql)

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
                    completed_at,
                    sensitivity,
                    source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.task_id),
                    record.intent,
                    record.status.value,
                    record.agent_name,
                    record.summary,
                    record.created_at.isoformat(),
                    record.completed_at.isoformat(),
                    record.sensitivity.value,
                    record.source.value,
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

        return self._to_record(row)

    def get_recent(
        self,
        limit: int = 10,
        intent: str | None = None,
        status: MemoryStatus | None = None,
        agent_name: str | None = None,
        offset: int = 0,
    ) -> list[EpisodicMemoryRecord]:
        """Retrieves a page of recent memories with optional filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if intent is not None:
            if not isinstance(intent, str):
                raise TypeError("Intent must be a string.")
            if not intent.strip():
                raise ValueError("Intent cannot be empty.")

        if status is not None and not isinstance(status, MemoryStatus):
            raise TypeError("Status must be a MemoryStatus value.")

        if agent_name is not None:
            if not isinstance(agent_name, str):
                raise TypeError("Agent name must be a string.")
            if not agent_name.strip():
                raise ValueError("Agent name cannot be empty.")

        conditions = []
        parameters = []

        if intent is not None:
            conditions.append("intent = ?")
            parameters.append(intent)

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)

        if agent_name is not None:
            conditions.append("agent_name = ?")
            parameters.append(agent_name)

        query = "SELECT * FROM episodic_memory"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY completed_at DESC, rowid DESC
            LIMIT ? OFFSET ?
        """

        parameters.extend([limit, offset])

        with self.database.connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row) -> EpisodicMemoryRecord:
        """Converts a database row into a validated memory record."""

        return EpisodicMemoryRecord(
            task_id=row["task_id"],
            intent=row["intent"],
            status=row["status"],
            agent_name=row["agent_name"],
            summary=row["summary"],
            created_at=row["created_at"],
            completed_at=row["completed_at"],
            sensitivity=MemorySensitivity(row["sensitivity"]),
            source=MemorySource(row["source"]),
        )
