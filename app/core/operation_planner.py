import os
from uuid import UUID, uuid4

from app.core.path_validator import (
    validate_path,
    reject_quarantine_path,
)
from app.core.schemas import (
    OperationAction,
    OperationPlan,
    OperationStatus,
)
from app.tools.quarantine_manager import (
    QUARANTINE_FOLDER,
    generate_quarantine_paths,
    load_quarantine_metadata,
)

def create_operation_plan(
    task_id: UUID,
    action: OperationAction,
    destination_path: str,

    source_path: str | None = None,
) -> OperationPlan:

    destination = validate_path(destination_path)
    destination = validate_path(destination_path)
    reject_quarantine_path(destination)

    if action == OperationAction.CREATE:
        if source_path is not None:
            raise ValueError("CREATE operations cannot have a source path.")

    elif action in (OperationAction.COPY, OperationAction.RENAME):
        if source_path is None:
            raise ValueError("This operation requires a source path.")

        source = validate_path(source_path, must_exist=True)
        reject_quarantine_path(source)
        if not source.is_file():
            raise ValueError("Source must be an existing file.")

    else:
        raise ValueError("Unsupported operation.")

    if destination.exists():
        raise ValueError("Destination already exists.")

    parent = validate_path(
        str(destination.parent),
        must_exist=True,
    )

    if not parent.is_dir():
        raise ValueError("Destination parent must be a directory.")

    return OperationPlan(
        task_id=task_id,
        action=action,
        source_path=str(source) if source_path is not None else None,
        destination_path=str(destination),
        dry_run=True,
        requires_approval=True,
    )

def create_rollback_plan(
    completed_operation: OperationPlan,
) -> OperationPlan:

    if completed_operation.action != OperationAction.RENAME:
        raise ValueError(
            "Rollback is currently supported only for RENAME operations."
        )

    if completed_operation.status != OperationStatus.EXECUTED:
        raise ValueError(
            "Only successfully executed operations can be rolled back."
        )

    rollback_data = completed_operation.rollback_data

    original_path = rollback_data.get("original_path")
    renamed_path = rollback_data.get("renamed_path")

    if not original_path or not renamed_path:
        raise ValueError("Rollback information is incomplete.")

    if completed_operation.destination_path != renamed_path:
        raise ValueError("Rollback information does not match the operation.")

    if completed_operation.source_path != original_path:
        raise ValueError("Original source information does not match.")

    # Create a new RENAME plan with reversed paths.
    return create_operation_plan(
        task_id=completed_operation.task_id,
        action=OperationAction.RENAME,
        source_path=renamed_path,
        destination_path=original_path,
    )

def create_quarantine_plan(
    task_id: UUID,
    source_path: str,
    approved_root: str,
) -> OperationPlan:

    root = validate_path(
        approved_root,
        must_exist=True,
    )

    if not root.is_dir():
        raise ValueError("Approved root must be a directory.")

    source = validate_path(
        source_path,
        must_exist=True,
    )

    if root not in source.parents:
        raise ValueError("Source must be inside the approved root.")

    if not source.is_file():
        raise ValueError("Source must be an existing regular file.")

    if QUARANTINE_FOLDER in source.parts:
        raise ValueError("File is already inside quarantine storage.")

    operation_id = uuid4()

    quarantine_file, _ = generate_quarantine_paths(
        str(root),
        operation_id,
        source.name,
    )

    return OperationPlan(
        operation_id=operation_id,
        task_id=task_id,
        action=OperationAction.QUARANTINE,
        source_path=str(source),
        destination_path=str(quarantine_file),
        approved_root=str(root),
        dry_run=True,
        requires_approval=True,
    )


def create_restore_plan(
    task_id: UUID,
    quarantine_operation_id: UUID,
    approved_root: str,
) -> OperationPlan:

    root = validate_path(
        approved_root,
        must_exist=True,
    )

    if not root.is_dir():
        raise ValueError("Approved root must be a directory.")

    metadata = load_quarantine_metadata(
        str(root),
        quarantine_operation_id,
    )

    if metadata.status != "quarantined":
        raise ValueError("File is not currently quarantined.")

    source = validate_path(
        metadata.quarantine_path,
        must_exist=True,
    )

    destination = validate_path(metadata.original_path)

    if not source.is_file():
        raise ValueError("Quarantined source must be a regular file.")

    if root not in destination.parents:
        raise ValueError("Restore destination is outside the approved root.")

    if not destination.parent.is_dir():
        raise ValueError("Original destination directory no longer exists.")

    if os.path.lexists(destination):
        raise ValueError("Original destination already exists.")

    return OperationPlan(
        task_id=task_id,
        action=OperationAction.RESTORE,
        source_path=str(source),
        destination_path=str(destination),
        approved_root=str(root),
        related_operation_id=quarantine_operation_id,
        dry_run=True,
        requires_approval=True,
    )
