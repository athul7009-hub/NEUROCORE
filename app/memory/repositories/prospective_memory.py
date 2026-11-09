
from datetime import datetime, timezone
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.prospective_schemas import (
    ProspectiveMemoryPriority,
    ProspectiveMemoryRecord,
    ProspectiveMemorySource,
    ProspectiveMemoryStatus,
    ProspectiveTriggerType,
)
from app.memory.schemas import MemorySensitivity


class ProspectiveMemoryRepository:
    """Stores and retrieves future intentions and pending actions."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the prospective memory table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS prospective_memory (
                    memory_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    action TEXT NOT NULL,
                    trigger_type TEXT NOT NULL,
                    trigger_condition TEXT,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_agent TEXT NOT NULL,
                    source_task_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    due_at TEXT,
                    expires_at TEXT,
                    triggered_at TEXT,
                    completed_at TEXT,
                    is_protected INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            # Migrate databases created before triggered_at was added.
            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(prospective_memory)"
                ).fetchall()
            }

            if "triggered_at" not in columns:
                connection.execute(
                    """
                    ALTER TABLE prospective_memory
                    ADD COLUMN triggered_at TEXT
                    """
                )

            indexes = (
                """
                CREATE INDEX IF NOT EXISTS
                idx_prospective_memory_status
                ON prospective_memory(status)
                """,
                """
                CREATE INDEX IF NOT EXISTS
                idx_prospective_memory_due_at
                ON prospective_memory(due_at)
                """,
                """
                CREATE INDEX IF NOT EXISTS
                idx_prospective_memory_priority
                ON prospective_memory(priority)
                """,
                """
                CREATE INDEX IF NOT EXISTS
                idx_prospective_memory_source_agent
                ON prospective_memory(source_agent)
                """,
            )

            for statement in indexes:
                connection.execute(statement)

    def save(self, record: ProspectiveMemoryRecord) -> None:
        """Persists one prospective memory record."""

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO prospective_memory (
                    memory_id, title, description, action,
                    trigger_type, trigger_condition, priority,
                    status, sensitivity, source, source_agent,
                    source_task_id, created_at, updated_at,
                    due_at, expires_at, triggered_at,
                    completed_at, is_protected
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?
                )
                """,
                (
                    str(record.memory_id),
                    record.title,
                    record.description,
                    record.action,
                    record.trigger_type.value,
                    record.trigger_condition,
                    record.priority.value,
                    record.status.value,
                    record.sensitivity.value,
                    record.source.value,
                    record.source_agent,
                    (
                        str(record.source_task_id)
                        if record.source_task_id
                        else None
                    ),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    self._timestamp(record.due_at),
                    self._timestamp(record.expires_at),
                    self._timestamp(record.triggered_at),
                    self._timestamp(record.completed_at),
                    int(record.is_protected),
                ),
            )

    def get(
        self,
        memory_id: UUID,
    ) -> ProspectiveMemoryRecord | None:
        """Retrieves a prospective memory record by ID."""

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM prospective_memory
                WHERE memory_id = ?
                """,
                (str(memory_id),),
            ).fetchone()

        return self._to_record(row) if row else None
    def get_identity_status(
        self,
        memory_id: UUID,
    ) -> ProspectiveMemoryStatus | None:
        """Returns prospective memory status without retrieving content."""

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT status
                FROM prospective_memory
                WHERE memory_id = ?
                """,
                (str(memory_id),),
            ).fetchone()

        if row is None:
            return None

        return ProspectiveMemoryStatus(row["status"])
    def search(
        self,
        *,
        title: str | None = None,
        status: ProspectiveMemoryStatus | None = None,
        trigger_type: ProspectiveTriggerType | None = None,
        priority: ProspectiveMemoryPriority | None = None,
        sensitivity: MemorySensitivity | None = None,
        source: ProspectiveMemorySource | None = None,
        source_agent: str | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ProspectiveMemoryRecord]:
        """Searches intentions using optional exact filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        string_filters = {
            "title": title,
            "source_agent": source_agent,
        }

        for field, value in string_filters.items():
            if value is not None:
                if not isinstance(value, str):
                    raise TypeError(f"{field} must be a string.")

                if not value.strip():
                    raise ValueError(f"{field} cannot be empty.")

        enum_filters = (
            (status, ProspectiveMemoryStatus, "status"),
            (trigger_type, ProspectiveTriggerType, "trigger type"),
            (priority, ProspectiveMemoryPriority, "priority"),
            (sensitivity, MemorySensitivity, "sensitivity"),
            (source, ProspectiveMemorySource, "source"),
        )

        for value, expected_type, field in enum_filters:
            if value is not None and not isinstance(value, expected_type):
                raise TypeError(f"Invalid prospective memory {field}.")

        conditions = []
        parameters = []

        filters = (
            ("title", title),
            ("status", status),
            ("trigger_type", trigger_type),
            ("priority", priority),
            ("sensitivity", sensitivity),
            ("source", source),
            ("source_agent", source_agent),
        )

        for column, value in filters:
            if value is not None:
                conditions.append(f"{column} = ?")
                parameters.append(
                    value.value if hasattr(value, "value") else value
                )

        query = "SELECT * FROM prospective_memory"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

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

    def get_due(
        self,
        *,
        now: datetime | None = None,
        limit: int = 10,
    ) -> list[ProspectiveMemoryRecord]:
        """Retrieves pending time-based intentions whose due time has arrived.

        This method only identifies due intentions.
        It does not execute their actions or change their status.
        """

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        current_time = now or datetime.now(timezone.utc)

        if (
            not isinstance(current_time, datetime)
            or current_time.tzinfo is None
            or current_time.utcoffset() is None
        ):
            raise ValueError("Current time must be timezone-aware.")

        current_time = current_time.astimezone(timezone.utc).isoformat()

        with self.database.connection() as connection:
            rows = connection.execute(
                """
                SELECT *
                FROM prospective_memory
                WHERE status = ?
                  AND trigger_type = ?
                  AND due_at IS NOT NULL
                  AND due_at <= ?
                  AND (
                      expires_at IS NULL
                      OR expires_at > ?
                  )
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 0
                        WHEN 'high' THEN 1
                        WHEN 'normal' THEN 2
                        WHEN 'low' THEN 3
                    END,
                    due_at ASC,
                    rowid ASC
                LIMIT ?
                """,
                (
                    ProspectiveMemoryStatus.PENDING.value,
                    ProspectiveTriggerType.TIME.value,
                    current_time,
                    current_time,
                    limit,
                ),
            ).fetchall()

        return [self._to_record(row) for row in rows]

    def update(
        self,
        record: ProspectiveMemoryRecord,
        *,
        expected_status: ProspectiveMemoryStatus,
    ) -> bool:
        """Atomically updates an unprotected record in its expected state.

        Protection is immutable after creation and cannot be changed here.
        """

        if not isinstance(record, ProspectiveMemoryRecord):
            raise TypeError("Expected a ProspectiveMemoryRecord.")

        if not isinstance(expected_status, ProspectiveMemoryStatus):
            raise TypeError("Expected a valid prospective memory status.")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE prospective_memory
                SET title = ?,
                    description = ?,
                    action = ?,
                    trigger_type = ?,
                    trigger_condition = ?,
                    priority = ?,
                    status = ?,
                    sensitivity = ?,
                    source = ?,
                    source_agent = ?,
                    source_task_id = ?,
                    updated_at = ?,
                    due_at = ?,
                    expires_at = ?,
                    triggered_at = ?,
                    completed_at = ?
                WHERE memory_id = ?
                  AND status = ?
                  AND is_protected = 0
                """,
                (
                    record.title,
                    record.description,
                    record.action,
                    record.trigger_type.value,
                    record.trigger_condition,
                    record.priority.value,
                    record.status.value,
                    record.sensitivity.value,
                    record.source.value,
                    record.source_agent,
                    (
                        str(record.source_task_id)
                        if record.source_task_id
                        else None
                    ),
                    record.updated_at.isoformat(),
                    self._timestamp(record.due_at),
                    self._timestamp(record.expires_at),
                    self._timestamp(record.triggered_at),
                    self._timestamp(record.completed_at),
                    str(record.memory_id),
                    expected_status.value,
                ),
            )

        return cursor.rowcount == 1

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        """Converts an optional timestamp into ISO format."""

        return value.isoformat() if value is not None else None

    @staticmethod
    def _to_record(row) -> ProspectiveMemoryRecord:
        """Converts a database row into a validated record."""

        return ProspectiveMemoryRecord(
            memory_id=row["memory_id"],
            title=row["title"],
            description=row["description"],
            action=row["action"],
            trigger_type=ProspectiveTriggerType(row["trigger_type"]),
            trigger_condition=row["trigger_condition"],
            priority=ProspectiveMemoryPriority(row["priority"]),
            status=ProspectiveMemoryStatus(row["status"]),
            sensitivity=MemorySensitivity(row["sensitivity"]),
            source=ProspectiveMemorySource(row["source"]),
            source_agent=row["source_agent"],
            source_task_id=row["source_task_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            due_at=row["due_at"],
            expires_at=row["expires_at"],
            triggered_at=row["triggered_at"],
            completed_at=row["completed_at"],
            is_protected=bool(row["is_protected"]),
        )
