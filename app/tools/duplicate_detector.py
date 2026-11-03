
from collections import defaultdict


def find_duplicates(files: list[dict]) -> list[list[str]]:
    """Group files that share the same SHA-256 hash."""

    groups = defaultdict(list)

    for file in files:
        groups[file["sha256"]].append(file["path"])

    return [paths for paths in groups.values() if len(paths) > 1]
