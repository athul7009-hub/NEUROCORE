
import os
from pathlib import Path

from app.core.path_validator import validate_path


def copy_file(source_path: str, destination_path: str) -> Path:
    source = validate_path(source_path, must_exist=True)
    destination = validate_path(destination_path)

    if not source.is_file():
        raise ValueError("Source must be an existing file.")

    parent = validate_path(
        str(destination.parent),
        must_exist=True,
    )

    if not parent.is_dir():
        raise ValueError("Destination parent must be a directory.")

    if os.path.lexists(destination):
        raise ValueError("Destination already exists.")

    flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY

    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY

    file_descriptor = None
    created = False

    try:
        file_descriptor = os.open(destination, flags, 0o600)
        created = True

        with source.open("rb") as source_file:
            with os.fdopen(file_descriptor, "wb") as destination_file:
                file_descriptor = None

                for chunk in iter(
                    lambda: source_file.read(1024 * 1024),
                    b"",
                ):
                    destination_file.write(chunk)

        if not destination.is_file() or destination.is_symlink():
            raise ValueError("Copied file verification failed.")

        return destination

    except Exception:
        if file_descriptor is not None:
            os.close(file_descriptor)

        if created:
            try:
                destination.unlink(missing_ok=True)
            except OSError:
                pass

        raise
