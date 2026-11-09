
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.meta_conflict_schemas import (
    MetaMemoryConflictRecord,
    MetaMemoryConflictStatus,
    MetaMemoryConflictType,
)
from datetime import datetime

class MetaMemoryConflictRepository:
    """Stores and retrieves conflicts between existing memories."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the conflict table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS meta_memory_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    memory_type_a TEXT NOT NULL,
                    memory_id_a TEXT NOT NULL,
                    memory_type_b TEXT NOT NULL,
                    memory_id_b TEXT NOT NULL,
                    conflict_type TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    rationale TEXT NOT NULL,
                    status TEXT NOT NULL,
                    detected_at TEXT NOT NULL,
                    reviewed_at TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_conflicts_status
                ON meta_memory_conflicts(status)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_conflicts_detected
                ON meta_memory_conflicts(detected_at)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_conflicts_memory_a
                ON meta_memory_conflicts(memory_type_a, memory_id_a)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_meta_conflicts_memory_b
                ON meta_memory_conflicts(memory_type_b, memory_id_b)
                """
            )

    def save(self, record: MetaMemoryConflictRecord) -> None:
        """Persists one conflict record."""

        if not isinstance(record, MetaMemoryConflictRecord):
            raise TypeError("Expected a MetaMemoryConflictRecord.")

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO meta_memory_conflicts (
                    conflict_id,
                    memory_type_a,
                    memory_id_a,
                    memory_type_b,
                    memory_id_b,
                    conflict_type,
                    confidence_score,
                    rationale,
                    status,
                    detected_at,
                    reviewed_at,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.conflict_id),
                    record.memory_type_a,
                    record.memory_id_a,
                    record.memory_type_b,
                    record.memory_id_b,
                    record.conflict_type.value,
                    record.confidence_score,
                    record.rationale,
                    record.status.value,
                    record.detected_at.isoformat(),
                    self._timestamp(record.reviewed_at),
                    record.created_at.isoformat(),
                    record.updated_at.isoformat(),
                ),
            )

    def get(
        self,
        conflict_id: UUID,
    ) -> MetaMemoryConflictRecord | None:
        """Retrieves a conflict by its ID."""

        if not isinstance(conflict_id, UUID):
            raise TypeError("conflict_id must be a UUID.")

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM meta_memory_conflicts
                WHERE conflict_id = ?
                """,
                (str(conflict_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        *,
        status: MetaMemoryConflictStatus | None = None,
        conflict_type: MetaMemoryConflictType | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[MetaMemoryConflictRecord]:
        """Searches conflicts using optional exact filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if (
            status is not None
            and not isinstance(status, MetaMemoryConflictStatus)
        ):
            raise TypeError("Invalid conflict status.")

        if (
            conflict_type is not None
            and not isinstance(conflict_type, MetaMemoryConflictType)
        ):
            raise TypeError("Invalid conflict type.")

        conditions = []
        parameters = []

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)

        if conflict_type is not None:
            conditions.append("conflict_type = ?")
            parameters.append(conflict_type.value)

        query = "SELECT * FROM meta_memory_conflicts"

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += """
            ORDER BY detected_at DESC, rowid DESC
            LIMIT ? OFFSET ?
        """

        parameters.extend([limit, offset])

        with self.database.connection() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return [self._to_record(row) for row in rows]

    def update(self, record: MetaMemoryConflictRecord) -> bool:
        """Updates conflict details without changing its identity."""

        if not isinstance(record, MetaMemoryConflictRecord):
            raise TypeError("Expected a MetaMemoryConflictRecord.")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memory_conflicts
                SET conflict_type = ?,
                    confidence_score = ?,
                    rationale = ?,
                    status = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE conflict_id = ?
                """,
                (
                    record.conflict_type.value,
                    record.confidence_score,
                    record.rationale,
                    record.status.value,
                    self._timestamp(record.reviewed_at),
                    record.updated_at.isoformat(),
                    str(record.conflict_id),
                ),
            )

        return cursor.rowcount == 1
    def transition_status(
        self,
        conflict_id: UUID,
        *,
        expected_status: MetaMemoryConflictStatus,
        new_status: MetaMemoryConflictStatus,
        reviewed_at: datetime,
    ) -> bool:
        """Atomically transitions a conflict if its current status matches."""

        if not isinstance(conflict_id, UUID):
            raise TypeError("conflict_id must be a UUID.")

        if not isinstance(expected_status, MetaMemoryConflictStatus):
            raise TypeError("Invalid expected conflict status.")

        if not isinstance(new_status, MetaMemoryConflictStatus):
            raise TypeError("Invalid new conflict status.")

        if not isinstance(reviewed_at, datetime):
            raise TypeError("reviewed_at must be a datetime.")

        allowed_transitions = {
            (
                MetaMemoryConflictStatus.DETECTED,
                MetaMemoryConflictStatus.CONFIRMED,
            ),
            (
                MetaMemoryConflictStatus.DETECTED,
                MetaMemoryConflictStatus.DISMISSED,
            ),
            (
                MetaMemoryConflictStatus.CONFIRMED,
                MetaMemoryConflictStatus.RESOLVED,
            ),
        }

        if (expected_status, new_status) not in allowed_transitions:
            raise ValueError("Invalid conflict lifecycle transition.")

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE meta_memory_conflicts
                SET status = ?,
                    reviewed_at = ?,
                    updated_at = ?
                WHERE conflict_id = ?
                  AND status = ?
                """,
                (
                    new_status.value,
                    reviewed_at.isoformat(),
                    reviewed_at.isoformat(),
                    str(conflict_id),
                    expected_status.value,
                ),
            )

        return cursor.rowcount == 1
    @staticmethod
    def _timestamp(value):
        return value.isoformat() if value is not None else None

    @staticmethod
    def _to_record(row) -> MetaMemoryConflictRecord:
        """Converts a database row into a validated record."""

        return MetaMemoryConflictRecord(
            conflict_id=row["conflict_id"],
            memory_type_a=row["memory_type_a"],
            memory_id_a=row["memory_id_a"],
            memory_type_b=row["memory_type_b"],
            memory_id_b=row["memory_id_b"],
            conflict_type=MetaMemoryConflictType(
                row["conflict_type"]
            ),
            confidence_score=row["confidence_score"],
            rationale=row["rationale"],
            status=MetaMemoryConflictStatus(row["status"]),
            detected_at=row["detected_at"],
            reviewed_at=row["reviewed_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
