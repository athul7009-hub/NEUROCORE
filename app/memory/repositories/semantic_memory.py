
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.schemas import MemorySensitivity
from app.memory.semantic_schemas import (
    SemanticMemoryRecord,
    SemanticMemorySource,
    SemanticMemoryStatus,
)


class SemanticMemoryRepository:
    """Stores and retrieves structured semantic knowledge."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the semantic memory table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS semantic_memory (
                    memory_id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    predicate TEXT NOT NULL,
                    object TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    source TEXT NOT NULL,
                    source_task_id TEXT,
                    source_reference TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    validated_at TEXT,
                    validated_by TEXT,
                    is_protected INTEGER NOT NULL DEFAULT 0
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_semantic_memory_subject
                ON semantic_memory(subject)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_semantic_memory_predicate
                ON semantic_memory(predicate)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_semantic_memory_status
                ON semantic_memory(status)
                """
            )

    def save(self, record: SemanticMemoryRecord) -> None:
        """Persists one semantic memory record."""

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO semantic_memory (
                    memory_id,
                    subject,
                    predicate,
                    object,
                    confidence,
                    status,
                    sensitivity,
                    source,
                    source_task_id,
                    source_reference,
                    created_at,
                    updated_at,
                    validated_at,
                    validated_by,
                    is_protected
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.memory_id),
                    record.subject,
                    record.predicate,
                    record.object,
                    record.confidence,
                    record.status.value,
                    record.sensitivity.value,
                    record.source.value,
                    (
                        str(record.source_task_id)
                        if record.source_task_id
                        else None
                    ),
                    record.source_reference,
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                    (
                        record.validated_at.isoformat()
                        if record.validated_at
                        else None
                    ),
                    record.validated_by,
                    int(record.is_protected),
                ),
            )

    def get(
        self,
        memory_id: UUID,
    ) -> SemanticMemoryRecord | None:
        """Retrieves semantic memory by its unique ID."""

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM semantic_memory
                WHERE memory_id = ?
                """,
                (str(memory_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        *,
        subject: str | None = None,
        predicate: str | None = None,
        status: SemanticMemoryStatus | None = None,
        sensitivity: MemorySensitivity | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[SemanticMemoryRecord]:
        """Searches semantic memories using optional exact filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        for name, value in (
            ("Subject", subject),
            ("Predicate", predicate),
        ):
            if value is not None:
                if not isinstance(value, str):
                    raise TypeError(f"{name} must be a string.")
                if not value.strip():
                    raise ValueError(f"{name} cannot be empty.")

        if status is not None and not isinstance(
            status, SemanticMemoryStatus
        ):
            raise TypeError("Invalid semantic memory status.")

        if sensitivity is not None and not isinstance(
            sensitivity, MemorySensitivity
        ):
            raise TypeError("Invalid memory sensitivity.")

        conditions = []
        parameters = []

        if subject is not None:
            conditions.append("subject = ?")
            parameters.append(subject)

        if predicate is not None:
            conditions.append("predicate = ?")
            parameters.append(predicate)

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)

        if sensitivity is not None:
            conditions.append("sensitivity = ?")
            parameters.append(sensitivity.value)

        query = "SELECT * FROM semantic_memory"

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

    def update(self, record: SemanticMemoryRecord) -> bool:
        """Updates an existing semantic memory record."""

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE semantic_memory
                SET subject = ?,
                    predicate = ?,
                    object = ?,
                    confidence = ?,
                    status = ?,
                    sensitivity = ?,
                    source = ?,
                    source_task_id = ?,
                    source_reference = ?,
                    updated_at = ?,
                    validated_at = ?,
                    validated_by = ?,
                    is_protected = ?
                WHERE memory_id = ?
                """,
                (
                    record.subject,
                    record.predicate,
                    record.object,
                    record.confidence,
                    record.status.value,
                    record.sensitivity.value,
                    record.source.value,
                    (
                        str(record.source_task_id)
                        if record.source_task_id
                        else None
                    ),
                    record.source_reference,
                    record.updated_at.isoformat(),
                    (
                        record.validated_at.isoformat()
                        if record.validated_at
                        else None
                    ),
                    record.validated_by,
                    int(record.is_protected),
                    str(record.memory_id),
                ),
            )

        return cursor.rowcount == 1

    @staticmethod
    def _to_record(row) -> SemanticMemoryRecord:
        """Converts a database row into a validated record."""

        return SemanticMemoryRecord(
            memory_id=row["memory_id"],
            subject=row["subject"],
            predicate=row["predicate"],
            object=row["object"],
            confidence=row["confidence"],
            status=SemanticMemoryStatus(row["status"]),
            sensitivity=MemorySensitivity(row["sensitivity"]),
            source=SemanticMemorySource(row["source"]),
            source_task_id=row["source_task_id"],
            source_reference=row["source_reference"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            validated_at=row["validated_at"],
            validated_by=row["validated_by"],
            is_protected=bool(row["is_protected"]),
        )
