
import json
from datetime import datetime, timezone
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.schemas import MemorySensitivity
from app.memory.working_schemas import (
    WorkingMemoryEntryType,
    WorkingMemoryRecord,
)


class WorkingMemoryRepository:
    """Stores and retrieves temporary task-scoped working memory."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the working memory table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS working_memory (
                    entry_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_working_memory_task
                ON working_memory(task_id)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_working_memory_expiry
                ON working_memory(expires_at)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_working_memory_task_key
                ON working_memory(task_id, key)
                """
            )

    def save(self, record: WorkingMemoryRecord) -> None:
        """Persists one working memory entry."""

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO working_memory (
                    entry_id,
                    task_id,
                    key,
                    entry_type,
                    content,
                    source_agent,
                    sensitivity,
                    created_at,
                    updated_at,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.entry_id),
                    str(record.task_id),
                    record.key,
                    record.entry_type.value,
                    json.dumps(record.content),
                    record.source_agent,
                    record.sensitivity.value,
                    self._utc_iso(record.created_at),
                    self._utc_iso(record.updated_at),
                    self._utc_iso(record.expires_at),
                ),
            )

    def get(
        self,
        entry_id: UUID,
        task_id: UUID,
    ) -> WorkingMemoryRecord | None:
        """Retrieves an unexpired entry within its owning task."""

        now = datetime.now(timezone.utc).isoformat()

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM working_memory
                WHERE entry_id = ?
                  AND task_id = ?
                  AND expires_at > ?
                """,
                (str(entry_id), str(task_id), now),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        *,
        task_id: UUID,
        entry_type: WorkingMemoryEntryType | None = None,
        source_agent: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[WorkingMemoryRecord]:
        """Retrieves unexpired entries belonging to one task."""

        if not isinstance(task_id, UUID):
            raise TypeError("Task ID must be a UUID.")

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if entry_type is not None and not isinstance(
            entry_type, WorkingMemoryEntryType
        ):
            raise TypeError("Invalid working memory entry type.")

        if source_agent is not None:
            if not isinstance(source_agent, str):
                raise TypeError("Source agent must be a string.")
            if not source_agent.strip():
                raise ValueError("Source agent cannot be empty.")

        conditions = [
            "task_id = ?",
            "expires_at > ?",
        ]
        parameters = [
            str(task_id),
            datetime.now(timezone.utc).isoformat(),
        ]

        if entry_type is not None:
            conditions.append("entry_type = ?")
            parameters.append(entry_type.value)

        if source_agent is not None:
            conditions.append("source_agent = ?")
            parameters.append(source_agent)

        query = """
            SELECT *
            FROM working_memory
            WHERE
        """ + " AND ".join(conditions)

        query += """
            ORDER BY created_at DESC, rowid DESC
            LIMIT ? OFFSET ?
        """

        parameters.extend([limit, offset])

        with self.database.connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [self._to_record(row) for row in rows]

    def update(self, record: WorkingMemoryRecord) -> bool:
        """Updates an existing entry without changing its identity."""

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE working_memory
                SET key = ?,
                    entry_type = ?,
                    content = ?,
                    source_agent = ?,
                    sensitivity = ?,
                    updated_at = ?,
                    expires_at = ?
                WHERE entry_id = ?
                  AND task_id = ?
                """,
                (
                    record.key,
                    record.entry_type.value,
                    json.dumps(record.content),
                    record.source_agent,
                    record.sensitivity.value,
                    self._utc_iso(record.updated_at),
                    self._utc_iso(record.expires_at),
                    str(record.entry_id),
                    str(record.task_id),
                ),
            )

        return cursor.rowcount == 1

    def delete_expired(self) -> int:
        """Deletes expired entries and returns the deletion count."""

        now = datetime.now(timezone.utc).isoformat()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                DELETE FROM working_memory
                WHERE expires_at <= ?
                """,
                (now,),
            )

        return cursor.rowcount

    @staticmethod
    def _utc_iso(value: datetime) -> str:
        """Normalizes an aware timestamp to UTC ISO format."""

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Timestamp must be timezone-aware.")

        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _to_record(row) -> WorkingMemoryRecord:
        """Converts a database row into a validated record."""

        return WorkingMemoryRecord(
            entry_id=row["entry_id"],
            task_id=row["task_id"],
            key=row["key"],
            entry_type=WorkingMemoryEntryType(row["entry_type"]),
            content=json.loads(row["content"]),
            source_agent=row["source_agent"],
            sensitivity=MemorySensitivity(row["sensitivity"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            expires_at=row["expires_at"],
        )

