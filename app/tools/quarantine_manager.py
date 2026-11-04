
import os
import json
from pathlib import Path
from uuid import UUID, uuid4
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.path_validator import validate_path


QUARANTINE_FOLDER = ".neurocore_quarantine"


class QuarantineMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID
    original_path: str
    quarantine_path: str
    original_filename: str
    file_size: int = Field(ge=0)
    quarantined_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    status: Literal["quarantined", "restored"] = "quarantined"


def ensure_quarantine_storage(
    approved_root: str,
) -> tuple[Path, Path]:

    root = validate_path(
        approved_root,
        must_exist=True,
    )

    if not root.is_dir():
        raise ValueError("Approved root must be a directory.")

    quarantine_root = root / QUARANTINE_FOLDER

    files_directory = quarantine_root / "files"
    metadata_directory = quarantine_root / "metadata"

    for directory in (
        quarantine_root,
        files_directory,
        metadata_directory,
    ):
        validated = validate_path(str(directory))

        if os.path.lexists(validated):
            if not validated.is_dir():
                raise ValueError(
                    "Quarantine storage path is not a directory."
                )
        else:
            validated.mkdir()

        # Revalidate after creation.
        validate_path(
            str(validated),
            must_exist=True,
        )

    return files_directory, metadata_directory


def generate_quarantine_paths(
    approved_root: str,
    operation_id: UUID,
    original_filename: str,
) -> tuple[Path, Path]:

    filename = Path(original_filename).name

    if not filename or filename in (".", ".."):
        raise ValueError("Invalid original filename.")

    files_directory, metadata_directory = (
        ensure_quarantine_storage(approved_root)
    )

    quarantine_file = (
        files_directory / f"{operation_id}_{filename}"
    )

    metadata_file = (
        metadata_directory / f"{operation_id}.json"
    )

    validate_path(str(quarantine_file))
    validate_path(str(metadata_file))

    if os.path.lexists(quarantine_file):
        raise ValueError("Quarantine file already exists.")

    if os.path.lexists(metadata_file):
        raise ValueError("Quarantine metadata already exists.")

    return quarantine_file, metadata_file


def _validate_metadata(
    approved_root: str,
    metadata: QuarantineMetadata,
) -> Path:

    root = validate_path(
        approved_root,
        must_exist=True,
    )

    if not root.is_dir():
        raise ValueError("Approved root must be a directory.")

    original = validate_path(metadata.original_path)

    if root not in original.parents:
        raise ValueError(
            "Original file must be inside the approved directory."
        )

    if original.name != metadata.original_filename:
        raise ValueError("Original filename does not match.")

    files_dir, metadata_dir = ensure_quarantine_storage(
        str(root)
    )

    expected_file = (
        files_dir
        / f"{metadata.operation_id}_{metadata.original_filename}"
    )

    expected_metadata = (
        metadata_dir
        / f"{metadata.operation_id}.json"
    )

    if Path(metadata.quarantine_path) != expected_file:
        raise ValueError("Invalid quarantine file path.")

    validate_path(str(expected_file))
    validate_path(str(expected_metadata))

    return expected_metadata


def save_quarantine_metadata(
    approved_root: str,
    metadata: QuarantineMetadata,
) -> Path:

    metadata_path = _validate_metadata(
        approved_root,
        metadata,
    )

    if os.path.lexists(metadata_path):
        raise ValueError("Metadata record already exists.")

    temporary_path = metadata_path.with_name(
        f".{metadata_path.name}.{uuid4().hex}.tmp"
    )

    try:
        with temporary_path.open(
            "x",
            encoding="utf-8",
        ) as file:
            file.write(
                metadata.model_dump_json(indent=4)
            )
            file.flush()
            os.fsync(file.fileno())

        if os.path.lexists(metadata_path):
            raise ValueError("Metadata record already exists.")

        os.replace(temporary_path, metadata_path)

    finally:
        temporary_path.unlink(missing_ok=True)

    return metadata_path


def load_quarantine_metadata(
    approved_root: str,
    operation_id: UUID,
) -> QuarantineMetadata:

    _, metadata_dir = ensure_quarantine_storage(
        approved_root
    )

    metadata_path = metadata_dir / f"{operation_id}.json"

    validate_path(
        str(metadata_path),
        must_exist=True,
    )

    if not metadata_path.is_file():
        raise ValueError("Metadata record is not a regular file.")

    try:
        data = json.loads(
            metadata_path.read_text(encoding="utf-8")
        )

        metadata = QuarantineMetadata.model_validate(data)

    except (OSError, ValueError) as error:
        raise ValueError(
            "Quarantine metadata is missing, invalid or unreadable."
        ) from error

    if metadata.operation_id != operation_id:
        raise ValueError("Metadata operation ID mismatch.")

    _validate_metadata(approved_root, metadata)

    return metadata


def update_quarantine_metadata(
    approved_root: str,
    operation_id: UUID,
    new_status: Literal["quarantined", "restored"],
) -> Path:

    if new_status not in ("quarantined", "restored"):
        raise ValueError("Invalid quarantine metadata status.")

    metadata = load_quarantine_metadata(
        approved_root,
        operation_id,
    )

    metadata.status = new_status

    metadata_path = _validate_metadata(
        approved_root,
        metadata,
    )

    temporary_path = metadata_path.with_name(
        f".{metadata_path.name}.{uuid4().hex}.tmp"
    )

    try:
        with temporary_path.open(
            "x",
            encoding="utf-8",
        ) as file:
            file.write(metadata.model_dump_json(indent=4))
            file.flush()
            os.fsync(file.fileno())

        os.replace(temporary_path, metadata_path)

    finally:
        temporary_path.unlink(missing_ok=True)

    return metadata_path
