
from datetime import datetime, timezone
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)


class MetaMemoryRepository:
    """Stores and retrieves metadata about existing memories."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the meta-memory table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meta_memory (
                    meta_id TEXT PRIMARY KEY,
                    memory_type TEXT NOT NULL,
                    memory_id TEXT NOT NULL,
                    quality_score REAL,
                    assessment_confidence REAL,
                    usage_count INTEGER NOT NULL DEFAULT 0,
                    last_retrieved_at TEXT,
                    staleness_status TEXT NOT NULL,
                    last_assessed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(memory_type, memory_id)
                )
                """
            )

            indexes = (
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_memory_type
                ON meta_memory(memory_type)
                """,
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_memory_staleness
                ON meta_memory(staleness_status)
                """,
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_memory_last_assessed
                ON meta_memory(last_assessed_at)
                """,
            )

            for statement in indexes:
                connection.execute(statement)

    def save(self, record: MetaMemoryRecord) -> None:
        """Persists one meta-memory record."""

        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("Expected a MetaMemoryRecord.")

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO meta_memory (
                    meta_id,
                    memory_type,
                    memory_id,
                    quality_score,
                    assessment_confidence,
                    usage_count,
                    last_retrieved_at,
                    staleness_status,
                    last_assessed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.meta_id),
                    record.memory_type.value,
                    record.memory_id,
                    record.quality_score,
                    record.assessment_confidence,
                    record.usage_count,
                    self._timestamp(record.last_retrieved_at),
                    record.staleness_status.value,
                    self._timestamp(record.last_assessed_at),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )

    def get(self, meta_id: UUID) -> MetaMemoryRecord | None:
        """Retrieves metadata by its unique ID."""

        if not isinstance(meta_id, UUID):
            raise TypeError("meta_id must be a UUID.")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM meta_memory
                WHERE meta_id = ?
                """,
                (str(meta_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def get_for_memory(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
    ) -> MetaMemoryRecord | None:
        """Retrieves metadata for an original memory."""

        if not isinstance(memory_type, MetaMemoryType):
            raise TypeError("Invalid meta-memory type.")

        self._validate_memory_id(memory_id)

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM meta_memory
                WHERE memory_type = ?
                  AND memory_id = ?
                """,
                (memory_type.value, memory_id),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        *,
        memory_type: MetaMemoryType | None = None,
        staleness_status: MetaMemoryStalenessStatus | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MetaMemoryRecord]:
        """Searches metadata using optional exact filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if (
            memory_type is not None
            and not isinstance(memory_type, MetaMemoryType)
        ):
            raise TypeError("Invalid meta-memory type.")

        if (
            staleness_status is not None
            and not isinstance(
                staleness_status,
                MetaMemoryStalenessStatus,
            )
        ):
            raise TypeError("Invalid staleness status.")

        conditions = []
        parameters = []

        if memory_type is not None:
            conditions.append("memory_type = ?")
            parameters.append(memory_type.value)

        if staleness_status is not None:
            conditions.append("staleness_status = ?")
            parameters.append(staleness_status.value)

        query = "SELECT * FROM meta_memory"

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

    def update(self, record: MetaMemoryRecord) -> bool:
        """Updates metadata without changing its identity or creation time."""

        if not isinstance(record, MetaMemoryRecord):
            raise TypeError("Expected a MetaMemoryRecord.")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memory
                SET quality_score = ?,
                    assessment_confidence = ?,
                    usage_count = ?,
                    last_retrieved_at = ?,
                    staleness_status = ?,
                    last_assessed_at = ?,
                    updated_at = ?
                WHERE meta_id = ?
                  AND memory_type = ?
                  AND memory_id = ?
                """,
                (
                    record.quality_score,
                    record.assessment_confidence,
                    record.usage_count,
                    self._timestamp(record.last_retrieved_at),
                    record.staleness_status.value,
                    self._timestamp(record.last_assessed_at),
                    record.updated_at.isoformat(),
                    str(record.meta_id),
                    record.memory_type.value,
                    record.memory_id,
                ),
            )

        return cursor.rowcount == 1

    def record_usage(
        self,
        memory_type: MetaMemoryType,
        memory_id: str,
        *,
        retrieved_at: datetime | None = None,
    ) -> bool:
        """Atomically increments usage for an existing metadata record.

        Does not create metadata automatically or modify the original memory.
        """

        if not isinstance(memory_type, MetaMemoryType):
            raise TypeError("Invalid meta-memory type.")

        self._validate_memory_id(memory_id)

        timestamp = retrieved_at or datetime.now(timezone.utc)

        if (
            not isinstance(timestamp, datetime)
            or timestamp.tzinfo is None
            or timestamp.utcoffset() is None
        ):
            raise ValueError("Retrieval time must be timezone-aware.")

        timestamp_value = timestamp.isoformat()
        updated_value = datetime.now(timezone.utc).isoformat()

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memory
                SET usage_count = usage_count + 1,
                    last_retrieved_at = ?,
                    updated_at = ?
                WHERE memory_type = ?
                  AND memory_id = ?
                """,
                (
                    timestamp_value,
                    updated_value,
                    memory_type.value,
                    memory_id,
                ),
            )

        return cursor.rowcount == 1

    @staticmethod
    def _validate_memory_id(memory_id: str) -> None:
        if not isinstance(memory_id, str):
            raise TypeError("memory_id must be a string.")

        if not memory_id.strip():
            raise ValueError("memory_id cannot be blank.")

        if len(memory_id) > 100:
            raise ValueError("memory_id cannot exceed 100 characters.")

    @staticmethod
    def _timestamp(value: datetime | None) -> str | None:
        return value.isoformat() if value is not None else None

    @staticmethod
    def _to_record(row) -> MetaMemoryRecord:
        """Converts a database row into a validated record."""

        return MetaMemoryRecord(
            meta_id=row["meta_id"],
            memory_type=MetaMemoryType(row["memory_type"]),
            memory_id=row["memory_id"],
            quality_score=row["quality_score"],
            assessment_confidence=row["assessment_confidence"],
            usage_count=row["usage_count"],
            last_retrieved_at=row["last_retrieved_at"],
            staleness_status=MetaMemoryStalenessStatus(
                row["staleness_status"]
            ),
            last_assessed_at=row["last_assessed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
