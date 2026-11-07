from datetime import datetime, timezone
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemorySensitivity,
    MemorySource,
    MemoryStatus,
)


class EpisodicMemoryRepository:
    """Stores and retrieves episodic task history."""

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
                    source TEXT NOT NULL DEFAULT 'legacy',
                    lifecycle_status TEXT NOT NULL DEFAULT 'active',
                    archived_at TEXT,
                    use_count INTEGER NOT NULL DEFAULT 0,
                    last_used_at TEXT,
                    usage_tracked INTEGER NOT NULL DEFAULT 0,
                    is_protected INTEGER NOT NULL DEFAULT 0
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
                    "ADD COLUMN source TEXT NOT NULL DEFAULT 'legacy'"
                ),
                "lifecycle_status": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN lifecycle_status TEXT NOT NULL "
                    "DEFAULT 'active'"
                ),
                "archived_at": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN archived_at TEXT"
                ),
                "use_count": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN use_count INTEGER NOT NULL DEFAULT 0"
                ),
                "last_used_at": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN last_used_at TEXT"
                ),
                "usage_tracked": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN usage_tracked INTEGER NOT NULL DEFAULT 0"
                ),
                "is_protected": (
                    "ALTER TABLE episodic_memory "
                    "ADD COLUMN is_protected INTEGER NOT NULL DEFAULT 0"
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
                    task_id, intent, status, agent_name, summary,
                    created_at, completed_at, sensitivity, source,
                    lifecycle_status, archived_at, use_count,
                    last_used_at, usage_tracked, is_protected
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    record.lifecycle_status.value,
                    (
                        record.archived_at.isoformat()
                        if record.archived_at else None
                    ),
                    record.use_count,
                    (
                        record.last_used_at.isoformat()
                        if record.last_used_at else None
                    ),
                    int(record.usage_tracked),
                    int(record.is_protected),
                ),
            )

    def get(
        self,
        task_id: UUID,
        *,
        include_archived: bool = False,
    ) -> EpisodicMemoryRecord | None:
        """Retrieves a memory by task ID."""

        query = "SELECT * FROM episodic_memory WHERE task_id = ?"

        if not include_archived:
            query += " AND lifecycle_status = 'active'"

        with self.database.connection() as connection:
            row = connection.execute(
                query,
                (str(task_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def get_recent(
        self,
        limit: int = 10,
        intent: str | None = None,
        status: MemoryStatus | None = None,
        agent_name: str | None = None,
        offset: int = 0,
        include_archived: bool = False,
    ) -> list[EpisodicMemoryRecord]:
        """Retrieves recent memories with optional filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if not isinstance(include_archived, bool):
            raise TypeError("include_archived must be a boolean.")

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

        if not include_archived:
            conditions.append("lifecycle_status = 'active'")

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

    def record_usage(self, task_id: UUID) -> bool:
        """Records actual use of an active memory."""

        now = datetime.now(timezone.utc).isoformat()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE episodic_memory
                SET use_count = use_count + 1,
                    last_used_at = ?,
                    usage_tracked = 1
                WHERE task_id = ?
                  AND lifecycle_status = 'active'
                """,
                (now, str(task_id)),
            )

        return cursor.rowcount == 1

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
            lifecycle_status=MemoryLifecycleStatus(
                row["lifecycle_status"]
            ),
            archived_at=row["archived_at"],
            use_count=row["use_count"],
            last_used_at=row["last_used_at"],
            usage_tracked=bool(row["usage_tracked"]),
            is_protected=bool(row["is_protected"]),
        )