
from pathlib import Path

from app.core.config import settings
from app.tools.file_scanner import scan_directory, validate_scan_root
from app.tools.file_hasher import calculate_hash
from app.tools.duplicate_detector import find_duplicates


def is_approved_directory(directory: Path) -> bool:
    """Check whether a directory is inside an approved root."""

    for allowed in settings.allowed_scan_roots:
        approved_root = Path(allowed).expanduser().resolve()

        if directory == approved_root or approved_root in directory.parents:
            return True

    return False


def run_scan(directory: str) -> dict:
    """Scan an approved directory and identify duplicate files."""

    root = validate_scan_root(directory)

    if not is_approved_directory(root):
        raise PermissionError("This directory has not been approved.")

    files, scan_warnings = scan_directory(str(root))

    # Hash only same-size candidates and record skipped files.
    size_groups = {}
    for file in files:
        size_groups.setdefault(file["size_bytes"], []).append(file)

    hash_skipped = []

    for group in size_groups.values():
        if len(group) < 2:
            continue

        for file in group:
            try:
                file["sha256"] = calculate_hash(str(root / file["path"]))

            except ValueError as error:
                category = "oversized"
                reason = str(error)

            except PermissionError as error:
                category = "access_denied"
                reason = str(error)

            except FileNotFoundError as error:
                category = "missing"
                reason = str(error)

            except OSError as error:
                category = "filesystem_error"
                reason = str(error)

            else:
                continue

            hash_skipped.append({
                "path": file["path"],
                "category": category,
                "reason": reason,
            })

    hashed_files = [file for file in files if "sha256" in file]
    duplicates = find_duplicates(hashed_files)

    # Calculate file-type distribution.
    extension_counts = {}
    for file in files:
        extension = file["extension"] or "[no extension]"
        extension_counts[extension] = extension_counts.get(extension, 0) + 1

    # Calculate potentially recoverable storage.
    file_sizes = {file["path"]: file["size_bytes"] for file in files}

    recoverable_bytes = sum(
        file_sizes[path]
        for group in duplicates
        for path in group[1:]
    )



    return {
        "root": str(root),
        "total_files": len(files),
        "total_size_bytes": sum(file["size_bytes"] for file in files),
        "extension_counts": extension_counts,
        "duplicates": duplicates,
        "recoverable_bytes": recoverable_bytes,
        "hash_skipped": hash_skipped,
        "scan_warnings": scan_warnings,
        "files": files,
    }
