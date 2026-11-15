
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ScanDirectoryInput(BaseModel):
    directory: str = Field(min_length=1, max_length=1000)


class ScannedFile(BaseModel):
    name: str
    path: str
    extension: str
    size_bytes: int = Field(ge=0)
    sha256: str | None = None


class ScanWarning(BaseModel):
    path: str
    category: str
    reason: str


class HashSkippedFile(BaseModel):
    path: str
    category: str
    reason: str


class ScanDirectoryOutput(BaseModel):
    root: str
    total_files: int = Field(ge=0)
    total_size_bytes: int = Field(ge=0)
    extension_counts: dict[str, int]
    duplicates: list[list[str]]
    recoverable_bytes: int = Field(ge=0)
    hash_skipped: list[HashSkippedFile]
    scan_warnings: list[ScanWarning]
    files: list[ScannedFile]

class ToolDefinition(BaseModel):
    """Defines a registered tool and its execution policy."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)
    version: str = Field(
        default="1.0.0",
        min_length=1,
        max_length=30,
    )

    handler: Callable[..., Any]

    input_schema: type[BaseModel]
    output_schema: type[BaseModel]

    requires_approval: bool = True
    read_only: bool = False
