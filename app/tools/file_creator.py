
import os
import stat
from pathlib import Path

from app.core.path_validator import validate_path


def create_empty_file(destination_path: str) -> Path:
    destination = validate_path(destination_path)

    parent = validate_path(
        str(destination.parent),
        must_exist=True,
    )

    if not parent.is_dir():
        raise ValueError("Destination parent must be a directory.")

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    file_descriptor = None

    try:
        file_descriptor = os.open(destination, flags, 0o600)

        file_stat = os.fstat(file_descriptor)

        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("Created object is not a regular file.")

    except OSError as error:
        if error.errno == 17:  # File already exists on Windows and POSIX
            raise ValueError("Destination already exists.") from error

        raise ValueError(
            f"File creation failed: {error}"
        ) from error

    finally:
        if file_descriptor is not None:
            os.close(file_descriptor)

    if not destination.is_file() or destination.is_symlink():
        raise ValueError("File creation verification failed.")

    return destination
