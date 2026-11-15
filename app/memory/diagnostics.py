from app.memory.database import SQLiteDatabase
from app.memory.diagnostics_schemas import (
    MemoryDiagnosticsReport,
    MemoryTableDiagnostics,
)


class MemoryDiagnostics:
    """Provides read-only aggregate memory diagnostics."""

    TABLES = {
        "episodic": ("episodic_memory", "lifecycle_status"),
        "semantic": ("semantic_memory", "status"),
        "procedural": ("procedural_memory", "status"),
        "working": ("working_memory", None),
        "prospective": ("prospective_memory", "status"),
        "meta": ("meta_memories", "staleness_status"),
        "meta_conflicts": ("meta_memory_conflicts", "status"),
    }

    def __init__(self, database: SQLiteDatabase):
        if not isinstance(database, SQLiteDatabase):
            raise TypeError("Expected a SQLiteDatabase instance.")

        self.database = database

    def inspect(self) -> MemoryDiagnosticsReport:
        """Returns aggregate counts and database health."""

        memory_tables = {}

        with self.database.connection() as connection:
            for name, (table, status_column) in self.TABLES.items():
                total = connection.execute(
                    f"SELECT COUNT(*) FROM {table}"
                ).fetchone()[0]

                status_counts = {}

                if status_column is not None:
                    rows = connection.execute(
                        f"""
                        SELECT {status_column}, COUNT(*)
                        FROM {table}
                        GROUP BY {status_column}
                        """
                    ).fetchall()

                    status_counts = {
                        str(row[0]): row[1]
                        for row in rows
                    }

                memory_tables[name] = MemoryTableDiagnostics(
                    total_records=total,
                    status_counts=status_counts,
                )

        return MemoryDiagnosticsReport(
            database_integrity=self.database.check_integrity(),
            foreign_key_integrity=(
                self.database.check_foreign_key_integrity()
            ),
            memory_tables=memory_tables,
        )