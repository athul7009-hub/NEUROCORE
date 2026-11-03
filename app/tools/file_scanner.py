
from pathlib import Path
import os
import stat

EXCLUDED_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
}
def is_reparse_point(path: str) -> bool:
    """Detect Windows reparse points such as junctions and symlinks."""

    try:
        attributes = os.stat(
            path,
            follow_symlinks=False
        ).st_file_attributes

        return bool(
            attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT
        )

    except (AttributeError, OSError):
        return True

def validate_scan_root(directory: str) -> Path:
    """Validate a requested directory before scanning."""

    requested = Path(directory).expanduser().absolute()

    # Reject symbolic links in the requested path or its parents.
    if any(
    is_reparse_point(str(part))
    for part in [requested, *requested.parents]
    ):
        raise ValueError("Reparse-point paths are not allowed.")

    root = requested.resolve(strict=True)

    if not root.is_dir():
        raise ValueError("A valid directory is required.")

    if root == Path(root.anchor):
        raise ValueError("Drive-root scanning is not allowed.")

    protected_roots = [
        Path(os.environ.get("WINDIR", r"C:\Windows")),
        Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
        Path(os.environ.get("ProgramData", r"C:\ProgramData")),
    ]

    for protected in protected_roots:
        protected = protected.resolve()

        if root == protected or protected in root.parents:
            raise ValueError("Protected system locations cannot be scanned.")

    profile = Path(
        os.environ.get("USERPROFILE", str(Path.home()))
    ).resolve()

    if root == profile or root in profile.parents:
        raise ValueError("User-profile root and parent locations cannot be scanned.")

    return root


def scan_directory(
    directory: str, max_files: int = 10_000
) -> tuple[list[dict], list[dict]]:
    """Read file metadata without following symbolic links."""

    root = validate_scan_root(directory)

    files = []
    scan_warnings = []
    stack = [root]

    while stack:
        current = stack.pop()

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    if entry.is_symlink() or is_reparse_point(entry.path):
                        continue

                    path = Path(entry.path)

                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() not in EXCLUDED_DIRS:
                            stack.append(path)

                    elif entry.is_file(follow_symlinks=False):
                        if len(files) >= max_files:
                            raise ValueError(
                                f"Scan limit exceeded ({max_files} files)."
                            )

                        file_stat = entry.stat(follow_symlinks=False)

                        files.append({
                            "name": entry.name,
                            "path": str(path.relative_to(root)),
                            "extension": path.suffix.lower(),
                            "size_bytes": file_stat.st_size,
                        })

        except PermissionError:
            scan_warnings.append({
                "path": str(current.relative_to(root)),
                "category": "access_denied",
                "reason": "Permission denied while accessing directory.",
            })
    return files, scan_warnings
