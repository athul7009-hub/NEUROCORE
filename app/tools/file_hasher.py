
import ctypes
import hashlib
import ntpath
import os
import stat
from pathlib import Path

MAX_HASH_SIZE_BYTES = 100 * 1024 * 1024
CHUNK_SIZE_BYTES = 1024 * 1024

FILE_ATTRIBUTE_REPARSE_POINT = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10

FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000

GENERIC_READ = 0x80000000
FILE_SHARE_READ = 0x01
OPEN_EXISTING = 3
FILE_TYPE_DISK = 1


class UnsafeFileError(ValueError):
    """Raised when a file cannot be safely opened for hashing."""


def _validate_parent_components(
    path: Path,
    allowed_root: str | Path | None = None,
) -> Path | None:
    """Reject unsafe reparse points in parent directories."""

    from app.tools.file_scanner import (
        is_reparse_point,
        is_allowed_cloud_directory,
    )

    absolute_path = Path(os.path.abspath(path))
    root = None

    if allowed_root is not None:
        root = Path(allowed_root).resolve(strict=True)

        if not root.is_dir():
            raise ValueError("Approved root must be a directory.")

        try:
            relative = absolute_path.relative_to(root)
        except ValueError as error:
            raise UnsafeFileError(
                "File is outside the approved scan root."
            ) from error

        if not relative.parts:
            raise UnsafeFileError(
                "A directory cannot be hashed."
            )

    current = absolute_path.parent

    while current != root:
        if is_reparse_point(str(current)):
            if not is_allowed_cloud_directory(str(current)):
                raise UnsafeFileError(
                    "Unsafe reparse-point parent directory."
                )

        if current.parent == current:
            break

        current = current.parent

    return root


def _normalize_windows_path(path: str) -> str:
    """Normalize Windows paths returned by file handles."""

    if path.startswith("\\\\?\\UNC\\"):
        path = "\\\\" + path[8:]
    elif path.startswith("\\\\?\\"):
        path = path[4:]

    return ntpath.normcase(ntpath.normpath(path))


def _ensure_windows_path_within_root(
    actual_path: str,
    approved_root: Path,
) -> None:
    """Verify that an opened file resolves inside the approved root."""

    actual = _normalize_windows_path(actual_path)
    root = _normalize_windows_path(str(approved_root))

    try:
        common = ntpath.commonpath([actual, root])
    except ValueError as error:
        raise UnsafeFileError(
            "Opened file is outside the approved scan root."
        ) from error

    if common != root or actual == root:
        raise UnsafeFileError(
            "Opened file is outside the approved scan root."
        )


def _get_final_windows_path(handle, kernel32) -> str:
    """Get the actual path associated with an open Windows file handle."""

    get_final_path = kernel32.GetFinalPathNameByHandleW

    get_final_path.argtypes = [
        ctypes.c_void_p,
        ctypes.c_wchar_p,
        ctypes.c_uint32,
        ctypes.c_uint32,
    ]
    get_final_path.restype = ctypes.c_uint32

    size = 512

    while True:
        buffer = ctypes.create_unicode_buffer(size)

        length = get_final_path(
            handle,
            buffer,
            size,
            0,
        )

        if length == 0:
            raise ctypes.WinError(ctypes.get_last_error())

        if length < size:
            return buffer.value

        if length >= 32768:
            raise OSError("Resolved file path exceeds Windows path limits.")

        size = length + 1


def _open_windows_regular_file(
    path: Path,
    allowed_root: str | Path | None = None,
):
    """Open a regular Windows file without following its final reparse point."""

    import msvcrt
    from ctypes import wintypes

    approved_root = _validate_parent_components(
        path,
        allowed_root,
    )

    class FileAttributeTagInfo(ctypes.Structure):
        _fields_ = [
            ("FileAttributes", wintypes.DWORD),
            ("ReparseTag", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True,
    )

    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.c_void_p,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE

    get_info = kernel32.GetFileInformationByHandleEx
    get_info.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    get_info.restype = wintypes.BOOL

    get_file_type = kernel32.GetFileType
    get_file_type.argtypes = [wintypes.HANDLE]
    get_file_type.restype = wintypes.DWORD

    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL

    handle = create_file(
        str(path),
        GENERIC_READ,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_FLAG_OPEN_REPARSE_POINT | FILE_FLAG_SEQUENTIAL_SCAN,
        None,
    )

    invalid_handle = ctypes.c_void_p(-1).value

    if handle == invalid_handle:
        error = ctypes.get_last_error()

        if error == 5 and Path(path).is_dir():
            raise UnsafeFileError(
                "Directories cannot be hashed."
            )

        raise ctypes.WinError(error)

    transferred = False

    try:
        info = FileAttributeTagInfo()

        if not get_info(
            handle,
            9,
            ctypes.byref(info),
            ctypes.sizeof(info),
        ):
            raise ctypes.WinError(ctypes.get_last_error())

        if info.FileAttributes & FILE_ATTRIBUTE_REPARSE_POINT:
            raise UnsafeFileError(
                "Reparse-point files cannot be hashed."
            )

        if info.FileAttributes & FILE_ATTRIBUTE_DIRECTORY:
            raise UnsafeFileError(
                "Directories cannot be hashed."
            )

        if get_file_type(handle) != FILE_TYPE_DISK:
            raise UnsafeFileError(
                "Only regular disk files can be hashed."
            )

        if approved_root is not None:
            actual_path = _get_final_windows_path(
                handle,
                kernel32,
            )

            _ensure_windows_path_within_root(
                actual_path,
                approved_root,
            )

        descriptor = msvcrt.open_osfhandle(
            handle,
            os.O_RDONLY | os.O_BINARY | os.O_NOINHERIT,
        )
        transferred = True

        try:
            return os.fdopen(descriptor, "rb")
        except Exception:
            os.close(descriptor)
            raise

    finally:
        if not transferred:
            close_handle(handle)


def _open_regular_file(
    path: Path,
    allowed_root: str | Path | None = None,
):
    """Safely open a regular file without following its final symlink."""

    if os.name == "nt":
        return _open_windows_regular_file(path, allowed_root)

    approved_root = _validate_parent_components(
        path,
        allowed_root,
    )

    nofollow = getattr(os, "O_NOFOLLOW", None)

    if nofollow is None:
        raise OSError(
            "Safe no-follow file opening is unavailable."
        )

    descriptor = os.open(
        path,
        os.O_RDONLY | nofollow,
    )

    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise UnsafeFileError(
                "Only regular files can be hashed."
            )

        if approved_root is not None:
            fd_path = Path(f"/proc/self/fd/{descriptor}")

            if not fd_path.exists():
                raise OSError(
                    "Cannot verify the opened file's actual path."
                )

            actual_path = Path(os.path.realpath(fd_path))

            if not actual_path.is_relative_to(approved_root):
                raise UnsafeFileError(
                    "Opened file is outside the approved scan root."
                )

        return os.fdopen(descriptor, "rb")

    except Exception:
        os.close(descriptor)
        raise


def calculate_hash(
    file_path: str,
    *,
    allowed_root: str | Path | None = None,
) -> str:
    """Calculate SHA-256 with file and approved-root protections."""

    digest = hashlib.sha256()
    total_bytes = 0

    with _open_regular_file(
        Path(file_path),
        allowed_root,
    ) as file:
        while True:
            remaining = MAX_HASH_SIZE_BYTES - total_bytes

            chunk = file.read(
                min(CHUNK_SIZE_BYTES, remaining + 1)
            )

            if not chunk:
                break

            total_bytes += len(chunk)

            if total_bytes > MAX_HASH_SIZE_BYTES:
                raise ValueError(
                    "File exceeds the configured hashing size limit."
                )

            digest.update(chunk)

    return digest.hexdigest()
