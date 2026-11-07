
import json
from uuid import UUID

from app.memory.database import SQLiteDatabase
from app.memory.procedural_schemas import (
    ProceduralMemoryRecord,
    ProceduralMemorySource,
    ProceduralMemoryStatus,
)
from app.memory.schemas import MemorySensitivity


class ProceduralMemoryRepository:
    """Stores and retrieves reusable procedural knowledge."""

    def __init__(self, database: SQLiteDatabase):
        self.database = database

    def initialize(self) -> None:
        """Creates the procedural memory table and indexes."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS procedural_memory (
                    procedure_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    when_to_use TEXT NOT NULL,
                    steps TEXT NOT NULL,
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
                idx_procedural_memory_name
                ON procedural_memory(name)
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_procedural_memory_status
                ON procedural_memory(status)
                """
            )

    def save(self, record: ProceduralMemoryRecord) -> None:
        """Persists one procedural memory record."""

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO procedural_memory (
                    procedure_id, name, description, when_to_use,
                    steps, confidence, status, sensitivity, source,
                    source_task_id, source_reference, created_at,
                    updated_at, validated_at, validated_by, is_protected
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(record.procedure_id),
                    record.name,
                    record.description,
                    record.when_to_use,
                    self._serialize_steps(record),
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
        procedure_id: UUID,
    ) -> ProceduralMemoryRecord | None:
        """Retrieves a procedure by its unique ID."""

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM procedural_memory
                WHERE procedure_id = ?
                """,
                (str(procedure_id),),
            ).fetchone()

        return self._to_record(row) if row else None

    def search(
        self,
        *,
        name: str | None = None,
        status: ProceduralMemoryStatus | None = None,
        sensitivity: MemorySensitivity | None = None,
        limit: int = 10,
        offset: int = 0,
    ) -> list[ProceduralMemoryRecord]:
        """Searches procedures using optional exact filters."""

        if isinstance(limit, bool) or not isinstance(limit, int):
            raise TypeError("Limit must be an integer.")

        if not 1 <= limit <= 100:
            raise ValueError("Limit must be between 1 and 100.")

        if isinstance(offset, bool) or not isinstance(offset, int):
            raise TypeError("Offset must be an integer.")

        if offset < 0:
            raise ValueError("Offset cannot be negative.")

        if name is not None:
            if not isinstance(name, str):
                raise TypeError("Name must be a string.")

            if not name.strip():
                raise ValueError("Name cannot be empty.")

        if status is not None and not isinstance(
            status, ProceduralMemoryStatus
        ):
            raise TypeError("Invalid procedural memory status.")

        if sensitivity is not None and not isinstance(
            sensitivity, MemorySensitivity
        ):
            raise TypeError("Invalid memory sensitivity.")

        conditions = []
        parameters = []

        if name is not None:
            conditions.append("name = ?")
            parameters.append(name)

        if status is not None:
            conditions.append("status = ?")
            parameters.append(status.value)

        if sensitivity is not None:
            conditions.append("sensitivity = ?")
            parameters.append(sensitivity.value)

        query = "SELECT * FROM procedural_memory"

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

    def update(self, record: ProceduralMemoryRecord) -> bool:
        """Updates an existing procedural memory record."""

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE procedural_memory
                SET name = ?,
                    description = ?,
                    when_to_use = ?,
                    steps = ?,
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
                WHERE procedure_id = ?
                """,
                (
                    record.name,
                    record.description,
                    record.when_to_use,
                    self._serialize_steps(record),
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
                    str(record.procedure_id),
                ),
            )

        return cursor.rowcount == 1

    @staticmethod
    def _serialize_steps(record: ProceduralMemoryRecord) -> str:
        """Serializes procedure steps as JSON."""

        return json.dumps(
            [step.model_dump(mode="json") for step in record.steps]
        )

    @staticmethod
    def _to_record(row) -> ProceduralMemoryRecord:
        """Converts a database row into a validated record."""

        return ProceduralMemoryRecord(
            procedure_id=row["procedure_id"],
            name=row["name"],
            description=row["description"],
            when_to_use=row["when_to_use"],
            steps=json.loads(row["steps"]),
            confidence=row["confidence"],
            status=ProceduralMemoryStatus(row["status"]),
            sensitivity=MemorySensitivity(row["sensitivity"]),
            source=ProceduralMemorySource(row["source"]),
            source_task_id=row["source_task_id"],
            source_reference=row["source_reference"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            validated_at=row["validated_at"],
            validated_by=row["validated_by"],
            is_protected=bool(row["is_protected"]),
        )
