
import hashlib
from pathlib import Path

MAX_HASH_SIZE_BYTES = 100 * 1024 * 1024  # 100 MB


def calculate_hash(file_path: str) -> str:
    """Calculate a file's SHA-256 hash within the size limit."""

    digest = hashlib.sha256()
    total_bytes = 0

    with Path(file_path).open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            total_bytes += len(chunk)

            if total_bytes > MAX_HASH_SIZE_BYTES:
                raise ValueError("File exceeds the 100 MB hashing limit.")

            digest.update(chunk)

    return digest.hexdigest()
