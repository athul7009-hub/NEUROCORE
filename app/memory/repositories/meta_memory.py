
from datetime import datetime, timezone
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)


class MetaMemoryRepository:
    """Handles persistent storage and retrieval of meta-memory records."""

    MAX_LIMIT = 100

    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database
        self._create_table()

    def initialize(self) -> None:
        """Create or migrate the meta-memory table."""
        self._create_table()

    def _create_table(self) -> None:
        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meta_memories (
                    meta_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    task_id TEXT,
                    quality_score REAL,
                    assessment_confidence REAL,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    last_retrieved_at TEXT,
                    staleness_status TEXT NOT NULL DEFAULT 'unknown',
                    last_assessed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (memory_type, memory_id)
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(meta_memories)"
                ).fetchall()
            }

            if "task_id" not in columns:
                connection.execute(
                    "ALTER TABLE meta_memories ADD COLUMN task_id TEXT"
                )

    def save(self, record: MetaMemoryRecord) -> None:
        """Persist a meta-memory record."""
        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("record must be a MetaMemoryRecord")

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO meta_memories (
                    meta_id,
                    memory_type,
                    memory_id,
                    task_id,
                    quality_score,
                    assessment_confidence,
                    usage_count,
                    last_retrieved_at,
                    staleness_status,
                    last_assessed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.meta_id),
                    record.memory_type.value,
                    record.memory_id,
                    str(record.task_id) if record.task_id else None,
                    record.quality_score,
                    record.assessment_confidence,
                    record.usage_count,
                    self._timestamp(record.last_retrieved_at),
                    record.staleness_status.value,
                    self._timestamp(record.last_assessed_at),
                    self._timestamp(record.created_at),
                    self._timestamp(record.updated_at),
                ),
            )

    def get(self, meta_id: UUID) -> MetaMemoryRecord | None:
        """Retrieve a record by its metadata ID."""
        if not isinstance(meta_id, UUID):
            raise TypeError("meta_id must be a UUID")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM meta_memories
                WHERE meta_id = ?
                """,
                (str(meta_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def get_for_memory(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
        task_id: UUID | None = None,
    ) -> MetaMemoryRecord | None:
        """Retrieve metadata for a specific memory identity."""
        if not isinstance(memory_type, MetaMemoryType):
            raise TypeError("memory_type must be a MetaMemoryType")

        self._validate_memory_id(memory_id)

        if task_id is not None and not isinstance(task_id, UUID):
            raise TypeError("task_id must be a UUID or None")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM meta_memories
                WHERE memory_type = ?
                  AND memory_id = ?
                  AND task_id IS ?
                """,
                (
                    memory_type.value,
                    memory_id,
                    str(task_id) if task_id else None,
                ),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        memory_type: MetaMemoryType | None = None,
        *,
        staleness_status: MetaMemoryStalenessStatus | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MetaMemoryRecord]:
        """Search metadata records with optional filters and pagination."""
        if memory_type is not None and not isinstance(
            memory_type, MetaMemoryType
        ):
            raise TypeError("memory_type must be a MetaMemoryType or None")

        if staleness_status is not None and not isinstance(
            staleness_status, MetaMemoryStalenessStatus
        ):
            raise TypeError(
                "staleness_status must be a MetaMemoryStalenessStatus or None"
            )

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("limit must be an integer")

        if not 1 <= limit <= self.MAX_LIMIT:
            raise ValueError(
                f"limit must be between 1 and {self.MAX_LIMIT}"
            )

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("offset must be an integer")

        if offset < 0:
            raise ValueError("offset must be non-negative")

        conditions = []
        parameters = []

        if memory_type is not None:
            conditions.append("memory_type = ?")
            parameters.append(memory_type.value)

        if staleness_status is not None:
            conditions.append("staleness_status = ?")
            parameters.append(staleness_status.value)

        where_clause = (
            f"WHERE {' AND '.join(conditions)}" if conditions else ""
        )

        with self.database.connection() as connection:
            rows = connection.execute(
                f"""
                SELECT *
                FROM meta_memories
                {where_clause}
                ORDER BY julianday(created_at) DESC, rowid DESC
                LIMIT ? OFFSET ?
                """,
                (*parameters, limit, offset),
            ).fetchall()

        return [self._to_record(row) for row in rows]

    def update(self, record: MetaMemoryRecord) -> bool:
        """Update an existing record without changing its identity."""
        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("record must be a MetaMemoryRecord")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memories
                SET
                    quality_score = ?,
                    assessment_confidence = ?,
                    usage_count = ?,
                    last_retrieved_at = ?,
                    staleness_status = ?,
                    last_assessed_at = ?,
                    updated_at = ?
                WHERE meta_id = ?
                  AND memory_type = ?
                  AND memory_id = ?
                  AND task_id IS ?
                """,
                (
                    record.quality_score,
                    record.assessment_confidence,
                    record.usage_count,
                    self._timestamp(record.last_retrieved_at),
                    record.staleness_status.value,
                    self._timestamp(record.last_assessed_at),
                    self._timestamp(record.updated_at),
                    str(record.meta_id),
                    record.memory_type.value,
                    record.memory_id,
                    str(record.task_id) if record.task_id else None,
                ),
            )

        return cursor.rowcount > 0

    def update_assessment(
        self,
        meta_id: UUID,
        *,
        quality_score: float | None,
        assessment_confidence: float,
        staleness_status: MetaMemoryStalenessStatus,
        assessed_at: datetime,
        expected_usage_count: int,
    ) -> bool:
        """Persist assessment only if usage has not changed."""
        if not isinstance(meta_id, UUID):
            raise TypeError("meta_id must be a UUID")

        if (
            isinstance(expected_usage_count, bool)
            or not isinstance(expected_usage_count, int)
        ):
            raise TypeError("expected_usage_count must be an integer")

        if expected_usage_count < 0:
            raise ValueError("expected_usage_count cannot be negative")

        if quality_score is not None:
            if (
                isinstance(quality_score, bool)
                or not isinstance(quality_score, (int, float))
                or not 0 <= quality_score <= 1
            ):
                raise ValueError("quality_score must be between 0 and 1")

        if (
            isinstance(assessment_confidence, bool)
            or not isinstance(assessment_confidence, (int, float))
            or not 0 <= assessment_confidence <= 1
        ):
            raise ValueError(
                "assessment_confidence must be between 0 and 1"
            )

        if not isinstance(staleness_status, MetaMemoryStalenessStatus):
            raise TypeError(
                "staleness_status must be a MetaMemoryStalenessStatus"
            )

        if not isinstance(assessed_at, datetime):
            raise TypeError("assessed_at must be a datetime")

        if assessed_at.tzinfo is None or assessed_at.utcoffset() is None:
            raise ValueError("assessed_at must be timezone-aware")

        assessed_timestamp = assessed_at.astimezone(timezone.utc)
        now = datetime.now(timezone.utc)

        if assessed_timestamp > now:
            raise ValueError("assessed_at cannot be in the future")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memories
                SET
                    quality_score = ?,
                    assessment_confidence = ?,
                    staleness_status = ?,
                    last_assessed_at = ?,
                    updated_at = ?
                WHERE meta_id = ?
                  AND usage_count = ?
                """,
                (
                    quality_score,
                    assessment_confidence,
                    staleness_status.value,
                    assessed_timestamp.isoformat(),
                    now.isoformat(),
                    str(meta_id),
                    expected_usage_count,
                ),
            )

        return cursor.rowcount > 0

    
    def record_usage(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
        *,
        retrieved_at: datetime | None = None,
    ) -> bool:
        """Atomically record usage and invalidate the previous assessment."""
        if not isinstance(memory_type, MetaMemoryType):
            raise TypeError("memory_type must be a MetaMemoryType")

        self._validate_memory_id(memory_id)

        retrieved_at = (
            datetime.now(timezone.utc)
            if retrieved_at is None
            else retrieved_at
        )

        if not isinstance(retrieved_at, datetime):
            raise ValueError("retrieved_at must be a datetime")

        if retrieved_at.tzinfo is None or retrieved_at.utcoffset() is None:
            raise ValueError("retrieved_at must be timezone-aware")

        retrieved_timestamp = retrieved_at.astimezone(timezone.utc)

        now = datetime.now(timezone.utc)
        if retrieved_timestamp > now:
            raise ValueError("retrieved_at cannot be in the future")

        retrieved_value = retrieved_timestamp.isoformat()
        updated_value = now.isoformat()

        with self.database.connection() as connection:
            # Retry if another operation changes the timestamp between
            # reading it and updating the record.
            for _ in range(5):
                current = connection.execute(
                    """
                    SELECT last_retrieved_at
                    FROM meta_memories
                    WHERE memory_type = ?
                      AND memory_id = ?
                    """,
                    (memory_type.value, memory_id),
                ).fetchone()

                if current is None:
                    return False

                stored_value = current["last_retrieved_at"]

                if stored_value is None:
                    next_value = retrieved_value
                else:
                    stored_timestamp = datetime.fromisoformat(stored_value)

                    if (
                        stored_timestamp.tzinfo is None
                        or stored_timestamp.utcoffset() is None
                    ):
                        raise ValueError(
                            "Stored retrieval timestamp must be timezone-aware."
                        )

                    if (
                        stored_timestamp.astimezone(timezone.utc)
                        < retrieved_timestamp
                    ):
                        next_value = retrieved_value
                    else:
                        next_value = stored_value

                cursor = connection.execute(
                    """
                    UPDATE meta_memories
                    SET
                        usage_count = usage_count + 1,
                        last_retrieved_at = ?,
                        quality_score = NULL,
                        assessment_confidence = NULL,
                        staleness_status = ?,
                        last_assessed_at = NULL,
                        updated_at = ?
                    WHERE memory_type = ?
                      AND memory_id = ?
                      AND last_retrieved_at IS ?
                    """,
                    (
                        next_value,
                        MetaMemoryStalenessStatus.UNKNOWN.value,
                        updated_value,
                        memory_type.value,
                        memory_id,
                        stored_value,
                    ),
                )

                if cursor.rowcount == 1:
                    return True

        return False


    @staticmethod
    def _validate_memory_id(memory_id: str) -> None:
        if not isinstance(memory_id, str) or not memory_id.strip():
            raise ValueError("memory_id must be a non-empty string")

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        if value is None:
            return None

        if not isinstance(value, datetime):
            raise TypeError("timestamp must be a datetime or None")

        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")

        return value.astimezone(timezone.utc).isoformat()

    @staticmethod
    def _to_record(row) -> MetaMemoryRecord:
        """Convert a database row into a validated record."""
        return MetaMemoryRecord(
            meta_id=UUID(row["meta_id"]),
            memory_type=MetaMemoryType(row["memory_type"]),
            memory_id=row["memory_id"],
            task_id=(
                UUID(row["task_id"])
                if row["task_id"]
                else None
            ),
            quality_score=row["quality_score"],
            assessment_confidence=row["assessment_confidence"],
            usage_count=row["usage_count"],
            last_retrieved_at=(
                datetime.fromisoformat(row["last_retrieved_at"])
                if row["last_retrieved_at"]
                else None
            ),
            staleness_status=MetaMemoryStalenessStatus(
                row["staleness_status"]
            ),
            last_assessed_at=(
                datetime.fromisoformat(row["last_assessed_at"])
                if row["last_assessed_at"]
                else None
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
