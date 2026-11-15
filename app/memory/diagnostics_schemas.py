from pydantic import BaseModel, ConfigDict


class MemoryTableDiagnostics(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_records: int
    status_counts: dict[str, int]


class MemoryDiagnosticsReport(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_integrity: bool
    foreign_key_integrity: bool
    memory_tables: dict[str, MemoryTableDiagnostics]