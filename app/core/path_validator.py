import os
import stat
from pathlib import Path

from app.core.config import settings


REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def is_reparse_point(path: Path) -> bool:
    try:
        file_stat = os.lstat(path)

        attributes = getattr(file_stat, "st_file_attributes", 0)

        return (
            stat.S_ISLNK(file_stat.st_mode)
            or bool(attributes & REPARSE_POINT)
        )

    except OSError as error:
        raise ValueError(
            f"Unable to inspect path safely: {path}"
        ) from error


def check_path_components(path: Path):
    current = Path(path.anchor)

    for part in path.parts[1:]:
        current = current / part

        if os.path.lexists(current):
            if is_reparse_point(current):
                raise ValueError(
                    f"Symbolic links and reparse points are not allowed: {current}"
                )


def validate_path(path: str, must_exist: bool = False) -> Path:
    requested_path = Path(path).expanduser()

    if not requested_path.is_absolute():
        raise ValueError("Absolute paths are required.")

    if ".." in requested_path.parts:
        raise ValueError("Directory traversal is not allowed.")

    requested_path = Path(os.path.abspath(requested_path))

    approved_roots = []

    for root_string in settings.allowed_scan_roots:
        root = Path(root_string).expanduser()

        if not root.is_absolute() or ".." in root.parts:
            raise ValueError("Invalid approved directory configuration.")

        root = Path(os.path.abspath(root))

        check_path_components(root)

        if not root.is_dir():
            raise ValueError(
                f"Approved directory does not exist: {root}"
            )

        approved_roots.append(root)

    if not approved_roots:
        raise ValueError("No approved directories are configured.")

    is_approved = any(
        requested_path == root or root in requested_path.parents
        for root in approved_roots
    )

    if not is_approved:
        raise ValueError("Path is outside approved directories.")

    check_path_components(requested_path)

    if must_exist and not requested_path.exists():
        raise ValueError("The requested path does not exist.")

    return requested_path

def reject_quarantine_path(path: Path) -> None:
    if any(
        part.casefold() == ".neurocore_quarantine"
        for part in path.parts
    ):
        raise ValueError(
            "Ordinary operations cannot access quarantine storage."
        )
