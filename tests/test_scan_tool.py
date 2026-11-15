
import pytest
from pydantic import ValidationError

from app.tools.scan_tool import (
    SCAN_DIRECTORY_TOOL,
    scan_directory_tool,
)
from app.tools.tool_schemas import ScanDirectoryInput


def test_scan_tool_definition():
    assert SCAN_DIRECTORY_TOOL.name == "scan_directory"
    assert SCAN_DIRECTORY_TOOL.read_only is True
    assert SCAN_DIRECTORY_TOOL.requires_approval is False


def test_scan_directory_tool_validates_output(monkeypatch):
    expected = {
        "root": "C:/approved/test",
        "total_files": 1,
        "total_size_bytes": 100,
        "extension_counts": {".txt": 1},
        "duplicates": [],
        "recoverable_bytes": 0,
        "hash_skipped": [],
        "scan_warnings": [],
        "files": [
            {
                "name": "test.txt",
                "path": "test.txt",
                "extension": ".txt",
                "size_bytes": 100,
            }
        ],
    }

    monkeypatch.setattr(
        "app.tools.scan_tool.run_scan",
        lambda directory: expected,
    )

    result = scan_directory_tool(
        ScanDirectoryInput(directory="C:/approved/test")
    )

    assert result.total_files == 1
    assert result.files[0].name == "test.txt"


def test_scan_directory_tool_rejects_invalid_output(monkeypatch):
    monkeypatch.setattr(
        "app.tools.scan_tool.run_scan",
        lambda directory: {"invalid": "data"},
    )

    with pytest.raises(ValidationError):
        scan_directory_tool(
            ScanDirectoryInput(directory="C:/approved/test")
        )


def test_scan_directory_tool_propagates_permission_error(monkeypatch):
    def reject_scan(directory):
        raise PermissionError("Directory not approved.")

    monkeypatch.setattr(
        "app.tools.scan_tool.run_scan",
        reject_scan,
    )

    with pytest.raises(PermissionError):
        scan_directory_tool(
            ScanDirectoryInput(directory="C:/restricted")
        )
