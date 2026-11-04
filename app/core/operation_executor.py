
import os
import filecmp
from pathlib import Path
from uuid import UUID

from app.tools.file_copier import copy_file
from app.tools.file_creator import create_empty_file

from app.core.approval_manager import ApprovalManager
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
    QuarantineMetadata,
    generate_quarantine_paths,
    save_quarantine_metadata,
    load_quarantine_metadata,
    update_quarantine_metadata,
)


class OperationExecutor:

    def __init__(self, approval_manager: ApprovalManager):
        self.approval_manager = approval_manager

    def validate_quarantine_operation(
        self,
        operation: OperationPlan,
    ) -> tuple[Path, Path]:

        if not operation.approved_root:
            raise ValueError("Approved root is required.")

        root = validate_path(
            operation.approved_root,
            must_exist=True,
        )

        if not root.is_dir():
            raise ValueError("Approved root must be a directory.")

        if operation.action == OperationAction.QUARANTINE:

            if not operation.source_path:
                raise ValueError("Source path is required.")

            source = validate_path(
                operation.source_path,
                must_exist=True,
            )

            if root not in source.parents:
                raise ValueError("Source is outside the approved root.")

            if not source.is_file():
                raise ValueError("Source must be a regular file.")

            expected_file, _ = generate_quarantine_paths(
                str(root),
                operation.operation_id,
                source.name,
            )

            if Path(operation.destination_path) != expected_file:
                raise ValueError("Invalid quarantine destination.")

            return source, expected_file

        if operation.action == OperationAction.RESTORE:

            if not operation.related_operation_id:
                raise ValueError(
                    "Original quarantine operation ID is required."
                )

            metadata = load_quarantine_metadata(
                str(root),
                operation.related_operation_id,
            )

            if metadata.status != "quarantined":
                raise ValueError("File is not currently quarantined.")

            if operation.source_path != metadata.quarantine_path:
                raise ValueError("Restore source does not match metadata.")

            if operation.destination_path != metadata.original_path:
                raise ValueError(
                    "Restore destination does not match metadata."
                )

            source = validate_path(
                metadata.quarantine_path,
                must_exist=True,
            )

            destination = validate_path(
                metadata.original_path,
            )

            if root not in destination.parents:
                raise ValueError(
                    "Restore destination is outside approved root."
                )

            if not source.is_file():
                raise ValueError(
                    "Quarantined source is not a regular file."
                )

            if source.stat().st_size != metadata.file_size:
                raise ValueError(
                    "Quarantined file size does not match metadata."
                )

            return source, destination

        raise ValueError("Unsupported quarantine operation.")

    def validate_execution(self, operation_id: UUID) -> OperationPlan:

        operation = self.approval_manager.operations.get(operation_id)

        if operation is None:
            raise ValueError("Operation not found.")

        if operation.status != OperationStatus.APPROVED:
            raise ValueError("Operation has not been approved.")

        if not self.approval_manager.is_authorized(operation_id):
            raise ValueError(
                "Operation approval is invalid or its plan was modified."
            )

        if operation.dry_run:
            raise ValueError(
                "Execution blocked: operation is in dry-run mode."
            )

        # QUARANTINE and RESTORE validation
        if operation.action in (
            OperationAction.QUARANTINE,
            OperationAction.RESTORE,
        ):
            _, destination = self.validate_quarantine_operation(operation)

            parent = validate_path(
                str(destination.parent),
                must_exist=True,
            )

            if not parent.is_dir():
                raise ValueError("Destination parent must be a directory.")

            if os.path.lexists(destination):
                raise ValueError("Destination already exists.")

            return operation

        # CREATE, COPY and RENAME validation
        destination = validate_path(operation.destination_path)
        reject_quarantine_path(destination)

        parent = validate_path(
            str(destination.parent),
            must_exist=True,
        )

        if not parent.is_dir():
            raise ValueError("Destination parent must be a directory.")

        if os.path.lexists(destination):
            raise ValueError("Destination already exists.")

        if operation.action in (
            OperationAction.COPY,
            OperationAction.RENAME,
        ):
            if not operation.source_path:
                raise ValueError("Source path is required.")

            source = validate_path(
                operation.source_path,
                must_exist=True,
            )
            reject_quarantine_path(source)
            if not source.is_file():
                raise ValueError("Source must be an existing regular file.")

            if source == destination:
                raise ValueError("Source and destination cannot be identical.")

        elif operation.action != OperationAction.CREATE:
            raise ValueError("Unsupported operation.")

        return operation

    def execute(self, operation_id: UUID) -> Path:

        operation = self.validate_execution(operation_id)

        try:

            # CREATE
            if operation.action == OperationAction.CREATE:

                result = create_empty_file(
                    operation.destination_path
                )

                if (
                    not result.is_file()
                    or result.is_symlink()
                    or result.stat().st_size != 0
                ):
                    raise ValueError("Created file verification failed.")

            # COPY
            elif operation.action == OperationAction.COPY:

                result = copy_file(
                    operation.source_path,
                    operation.destination_path,
                )

                if not filecmp.cmp(
                    operation.source_path,
                    result,
                    shallow=False,
                ):
                    raise ValueError("Copied file verification failed.")

            # RENAME
            elif operation.action == OperationAction.RENAME:

                source = validate_path(
                    operation.source_path,
                    must_exist=True,
                )

                destination = validate_path(
                    operation.destination_path
                )

                os.rename(source, destination)

                if (
                    not destination.is_file()
                    or destination.is_symlink()
                    or source.exists()
                ):
                    raise ValueError("Renamed file verification failed.")

                operation.rollback_data = {
                    "original_path": str(source),
                    "renamed_path": str(destination),
                }

                result = destination

            # QUARANTINE
            elif operation.action == OperationAction.QUARANTINE:

                source, destination = self.validate_quarantine_operation(
                    operation
                )

                file_size = source.stat().st_size

                os.rename(source, destination)

                try:
                    if (
                        not destination.is_file()
                        or source.exists()
                        or destination.stat().st_size != file_size
                    ):
                        raise ValueError(
                        "Quarantine movement verification failed."
                 )

                except Exception as error:
                    try:
                        os.rename(destination, source)

                    except OSError as recovery_error:
                        raise RuntimeError(
                                "Quarantine verification failed and automatic recovery "
                                "also failed. The file may remain in quarantine."
                    ) from recovery_error

                    raise error

                metadata = QuarantineMetadata(
                    operation_id=operation.operation_id,
                    original_path=str(source),
                    quarantine_path=str(destination),
                    original_filename=source.name,
                    file_size=file_size,
                )

                try:
                    save_quarantine_metadata(
                        operation.approved_root,
                        metadata,
                    )

                except Exception as error:
                    try:
                        os.rename(destination, source)

                    except OSError as recovery_error:
                        raise RuntimeError(
                            "Metadata saving failed and automatic recovery "
                            "also failed. The file may remain in quarantine."
                        ) from recovery_error

                    raise RuntimeError(
                        "Metadata saving failed. The file was returned "
                        "to its original location."
                    ) from error

                result = destination

            # RESTORE
            elif operation.action == OperationAction.RESTORE:

                source, destination = self.validate_quarantine_operation(
                    operation
                )

                metadata = load_quarantine_metadata(
                    operation.approved_root,
                    operation.related_operation_id,
                )

                
                os.rename(source, destination)

                try:
                    if (
                        not destination.is_file()
                        or source.exists()
                        or destination.stat().st_size != metadata.file_size
                    ):
                        raise ValueError("Restore movement verification failed.")

                except Exception as error:
                    try:
                        os.rename(destination, source)

                    except OSError as recovery_error:
                        raise RuntimeError(
                        "Restore verification failed and automatic recovery "
                        "also failed. The file may remain at its original location."
                        ) from recovery_error

                    raise error


                try:
                    update_quarantine_metadata(
                        operation.approved_root,
                        operation.related_operation_id,
                        "restored",
                    )

                except Exception as error:
                    try:
                        os.rename(destination, source)

                    except OSError as recovery_error:
                        raise RuntimeError(
                            "Metadata update failed and automatic recovery "
                            "also failed. The file may remain at its "
                            "original location."
                        ) from recovery_error

                    raise RuntimeError(
                        "Metadata update failed. The file was returned "
                        "to quarantine."
                    ) from error

                result = destination

            else:
                raise ValueError("Unsupported operation.")

            operation.status = OperationStatus.EXECUTED

            return result

        except Exception:
            operation.status = OperationStatus.FAILED
            raise
