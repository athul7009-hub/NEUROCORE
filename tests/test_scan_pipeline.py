
from app.tools.scan_pipeline import run_scan
from app.core.config import settings
import pytest
from app.tools.file_hasher import UnsafeFileError

def test_scan_pipeline_finds_duplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    (tmp_path / "first.txt").write_text("NEUROCORE")
    (tmp_path / "second.txt").write_text("NEUROCORE")
    (tmp_path / "other.txt").write_text("Different")

    result = run_scan(str(tmp_path))

    assert result["total_files"] == 3
    assert result["total_size_bytes"] > 0
    assert len(result["duplicates"]) == 1
    assert set(result["duplicates"][0]) == {
        "first.txt", "second.txt"
    }


def test_scan_pipeline_empty_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    result = run_scan(str(tmp_path))

    assert result["total_files"] == 0
    assert result["duplicates"] == []

def test_scan_report_calculations(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    (tmp_path / "first.txt").write_text("NEUROCORE")
    (tmp_path / "second.txt").write_text("NEUROCORE")
    (tmp_path / "script.py").write_text("print('hello')")
    (tmp_path / "README").write_text("Documentation")

    result = run_scan(str(tmp_path))

    assert result["extension_counts"] == {
        ".txt": 2,
        ".py": 1,
        "[no extension]": 1,
    }

    assert result["recoverable_bytes"] == len("NEUROCORE")

@pytest.mark.parametrize(
    ("error", "expected_category"),
    [
        (ValueError("Size limit"), "oversized"),
        (PermissionError("Access denied"), "access_denied"),
        (FileNotFoundError("File missing"), "missing"),
        (OSError("Filesystem issue"), "filesystem_error"),
        (UnsafeFileError("Unsafe reparse-point file"), "unsafe_file"),
    ],
)
def test_hash_errors_are_categorized(
    tmp_path, monkeypatch, error, expected_category
):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    (tmp_path / "first.txt").write_text("NEUROCORE")
    (tmp_path / "second.txt").write_text("NEUROCORE")

    def failing_hash(path, *, allowed_root=None):
        raise error

    monkeypatch.setattr(
        "app.tools.scan_pipeline.calculate_hash", failing_hash
    )

    result = run_scan(str(tmp_path))

    assert len(result["hash_skipped"]) == 2
    assert all(
        item["category"] == expected_category
        for item in result["hash_skipped"]
    )

def test_scan_pipeline_includes_scan_warnings(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    monkeypatch.setattr(
        "app.tools.scan_pipeline.scan_directory",
        lambda directory: (
            [],
            [{
                "path": "blocked",
                "category": "access_denied",
                "reason": "Permission denied",
            }],
        ),
    )

    result = run_scan(str(tmp_path))

    assert len(result["scan_warnings"]) == 1
    assert result["scan_warnings"][0]["category"] == "access_denied"

def test_cloud_placeholder_is_not_hashed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings, "allowed_scan_roots", [str(tmp_path)]
    )

    files = [
        {
            "name": "cloud.txt",
            "path": "cloud.txt",
            "extension": ".txt",
            "size_bytes": 8,
        },
        {
            "name": "local.txt",
            "path": "local.txt",
            "extension": ".txt",
            "size_bytes": 8,
        },
    ]

    monkeypatch.setattr(
        "app.tools.scan_pipeline.scan_directory",
        lambda directory: (files, []),
    )

    monkeypatch.setattr(
        "app.tools.scan_pipeline.is_allowed_cloud_file",
        lambda path: path.endswith("cloud.txt"),
    )

    hashed_paths = []

    def fake_hash(path, *, allowed_root=None):
        hashed_paths.append(path)
        return "a" * 64

    monkeypatch.setattr(
        "app.tools.scan_pipeline.calculate_hash",
        fake_hash,
    )

    result = run_scan(str(tmp_path))

    assert len(hashed_paths) == 1
    assert hashed_paths[0].endswith("local.txt")

    assert len(result["hash_skipped"]) == 1
    assert result["hash_skipped"][0]["category"] == "cloud_placeholder"
    assert result["hash_skipped"][0]["path"] == "cloud.txt"
