
import os
import stat
import ctypes
from pathlib import Path
from ctypes import wintypes
from contextlib import contextmanager


EXCLUDED_DIRS = {
    "$recycle.bin",
    "system volume information",
    "windows",
    "program files",
    "program files (x86)",
}

REPARSE_POINT = 0x400
DIRECTORY_ATTRIBUTE = 0x10

CLOUD_FILE_DIRECTORY_TAGS = {
    0x9000701A,  # CLOUD_7
    0x9000601A,  # CLOUD_6
    0x9000E01A,  # CLOUD_E
}


class FileAttributeTagInfo(ctypes.Structure):
    """Windows FILE_ATTRIBUTE_TAG_INFO structure."""

    _fields_ = [
        ("FileAttributes", wintypes.DWORD),
        ("ReparseTag", wintypes.DWORD),
    ]


def get_windows_file_attribute_tag(
    path: str,
) -> tuple[int, int]:
    """Read file attributes and reparse tag without following the point."""

    if os.name != "nt":
        raise OSError("Windows file inspection is unavailable.")

    with expose_cloud_placeholders():
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

        create_file = kernel32.CreateFileW
        create_file.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        ]
        create_file.restype = wintypes.HANDLE

        get_info = kernel32.GetFileInformationByHandleEx
        get_info.argtypes = [
            wintypes.HANDLE,
            ctypes.c_int,
            ctypes.POINTER(FileAttributeTagInfo),
            wintypes.DWORD,
        ]
        get_info.restype = wintypes.BOOL

        close_handle = kernel32.CloseHandle
        close_handle.argtypes = [wintypes.HANDLE]
        close_handle.restype = wintypes.BOOL

        handle = create_file(
            path,
            0x80,  # FILE_READ_ATTRIBUTES
            0x01 | 0x02 | 0x04,  # Share read, write and delete
            None,
            3,  # OPEN_EXISTING
            0x00200000 | 0x02000000,
            None,
        )

        if handle == wintypes.HANDLE(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())

        try:
            info = FileAttributeTagInfo()

            success = get_info(
                handle,
                9,  # FileAttributeTagInfo
                ctypes.byref(info),
                ctypes.sizeof(info),
            )

            if not success:
                raise ctypes.WinError(ctypes.get_last_error())

            return info.FileAttributes, info.ReparseTag

        finally:
            close_handle(handle)


def get_windows_reparse_tag(path: str) -> int | None:
    """Return the actual Windows reparse tag, if present."""

    attributes, tag = get_windows_file_attribute_tag(path)

    if not attributes & REPARSE_POINT:
        return None

    return tag


def is_reparse_point(path: str) -> bool:
    """Detect reparse points without following them."""

    try:
        if os.name == "nt":
            attributes, _ = get_windows_file_attribute_tag(path)
            return bool(attributes & REPARSE_POINT)

        return stat.S_ISLNK(os.lstat(path).st_mode)

    except FileNotFoundError:
        # A missing path cannot be traversed. Let the caller
        # handle the missing-path condition.
        return False

    except OSError:
        # Fail closed if inspection fails for another reason.
        return True


def is_allowed_cloud_directory(path: str) -> bool:
    """Allow only recognized Microsoft Cloud Files directories."""

    if os.name != "nt":
        return False

    try:
        attributes, tag = get_windows_file_attribute_tag(path)

        return (
            bool(attributes & REPARSE_POINT)
            and bool(attributes & DIRECTORY_ATTRIBUTE)
            and tag in CLOUD_FILE_DIRECTORY_TAGS
        )

    except OSError:
        return False


def is_allowed_cloud_file(path: str) -> bool:
    """Recognize Microsoft Cloud Files files without reading contents."""

    if os.name != "nt":
        return False

    try:
        attributes, tag = get_windows_file_attribute_tag(path)

        return (
            bool(attributes & REPARSE_POINT)
            and not bool(attributes & DIRECTORY_ATTRIBUTE)
            and tag in CLOUD_FILE_DIRECTORY_TAGS
        )

    except OSError:
        return False


def validate_scan_root(directory: str) -> Path:
    """Validate a requested directory before scanning."""

    requested = Path(directory).expanduser().absolute()

    # Reject unsupported reparse points in the requested path.
    if any(
        is_reparse_point(str(part))
        and not is_allowed_cloud_directory(str(part))
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
            raise ValueError(
                "Protected system locations cannot be scanned."
            )

    profile = Path(
        os.environ.get("USERPROFILE", str(Path.home()))
    ).resolve()

    if root == profile or root in profile.parents:
        raise ValueError(
            "User-profile root and parent locations cannot be scanned."
        )

    return root


def scan_directory(
    directory: str,
    max_files: int = 10_000,
) -> tuple[list[dict], list[dict]]:
    """Read file metadata without following unsafe reparse points."""

    if max_files < 1:
        raise ValueError("max_files must be at least 1.")

    root = validate_scan_root(directory)

    files = []
    scan_warnings = []
    stack = [root]
    limit_reached = False

    while stack and not limit_reached:
        current = stack.pop()

        # Revalidate the directory immediately before traversal.
        if is_reparse_point(str(current)) and not is_allowed_cloud_directory(
            str(current)
        ):
            continue

        try:
            with os.scandir(current) as entries:
                for entry in entries:
                    try:
                        if entry.is_symlink():
                            continue

                        is_directory = entry.is_dir(
                            follow_symlinks=False
                        )
                        is_file = entry.is_file(
                            follow_symlinks=False
                        )

                        # Reject unsupported reparse points.
                        if is_reparse_point(entry.path):
                            if is_directory:
                            # Never traverse nested directory reparse points,
                            # including recognized Cloud Files directories.
                                continue

                            if is_file:
                                if not is_allowed_cloud_file(entry.path):
                                    continue

                            else:
                                continue

                        path = Path(entry.path)

                        if is_directory:
                            if entry.name.casefold() not in EXCLUDED_DIRS:
                                stack.append(path)

                        elif is_file:
                            if len(files) >= max_files:
                                scan_warnings.append({
                                    "path": str(path.relative_to(root)),
                                    "category": "limit_reached",
                                    "reason": (
                                        f"Scan stopped at the "
                                        f"{max_files}-file limit."
                                    ),
                                })
                                limit_reached = True
                                break

                            file_stat = entry.stat(
                                follow_symlinks=False
                            )

                            files.append({
                                "name": entry.name,
                                "path": str(path.relative_to(root)),
                                "extension": path.suffix.lower(),
                                "size_bytes": file_stat.st_size,
                            })

                    except PermissionError:
                        scan_warnings.append({
                            "path": str(
                                Path(entry.path).relative_to(root)
                            ),
                            "category": "access_denied",
                            "reason": (
                                "Permission denied while inspecting entry."
                            ),
                        })

                    except FileNotFoundError:
                        scan_warnings.append({
                            "path": str(
                                Path(entry.path).relative_to(root)
                            ),
                            "category": "missing",
                            "reason": (
                                "File or directory disappeared "
                                "during scanning."
                            ),
                        })

                    except OSError:
                        scan_warnings.append({
                            "path": str(
                                Path(entry.path).relative_to(root)
                            ),
                            "category": "filesystem_error",
                            "reason": (
                                "Filesystem error while inspecting entry."
                            ),
                        })

                    if limit_reached:
                        break

        except PermissionError:
            scan_warnings.append({
                "path": str(current.relative_to(root)),
                "category": "access_denied",
                "reason": "Permission denied while accessing directory.",
            })

        except FileNotFoundError:
            scan_warnings.append({
                "path": str(current.relative_to(root)),
                "category": "missing",
                "reason": "Directory disappeared before traversal.",
            })

        except OSError:
            scan_warnings.append({
                "path": str(current.relative_to(root)),
                "category": "filesystem_error",
                "reason": "Filesystem error while accessing directory.",
            })

    return files, scan_warnings


@contextmanager
def expose_cloud_placeholders():
    """Temporarily expose Cloud Files placeholders on the current thread."""

    if os.name != "nt":
        raise OSError(
            "Cloud Files placeholder inspection requires Windows."
        )

    ntdll = ctypes.WinDLL("ntdll")

    set_mode = ntdll.RtlSetThreadPlaceholderCompatibilityMode
    set_mode.argtypes = [ctypes.c_byte]
    set_mode.restype = ctypes.c_byte

    previous_mode = set_mode(2)  # PHCM_EXPOSE_PLACEHOLDERS

    if previous_mode < 0:
        raise OSError(
            f"Could not expose Cloud Files placeholders: {previous_mode}"
        )

    try:
        yield

    finally:
        restored_mode = set_mode(previous_mode)

        if restored_mode < 0:
            raise OSError(
                f"Could not restore placeholder mode: {restored_mode}"
            )
