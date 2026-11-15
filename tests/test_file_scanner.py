
import pytest

from app.tools.file_scanner import scan_directory
import os

def test_scan_files(tmp_path):
    (tmp_path / "hello.py").write_text("print('hello')")
    (tmp_path / "notes.txt").write_text("NEUROCORE")
    (tmp_path / "subfolder").mkdir()
    (tmp_path / "subfolder" / "data.csv").write_text("a,b")

    files, warnings = scan_directory(str(tmp_path))

    assert len(files) == 3
    assert {file["name"] for file in files} == {
        "hello.py", "notes.txt", "data.csv"
    }
    assert warnings == []


def test_file_metadata(tmp_path):
    file = tmp_path / "example.py"
    file.write_text("hello")

    files, warnings = scan_directory(str(tmp_path))

    assert files[0]["extension"] == ".py"
    assert files[0]["size_bytes"] == 5
    assert files[0]["path"] == "example.py"
    assert warnings == []


def test_invalid_directory():
    with pytest.raises((FileNotFoundError, ValueError)):
        scan_directory("nonexistent_neurocore_folder")



def test_file_limit(tmp_path):
    (tmp_path / "one.txt").write_text("one")
    (tmp_path / "two.txt").write_text("two")

    files, warnings = scan_directory(str(tmp_path), max_files=1)

    assert len(files) == 1
    assert len(warnings) == 1
    assert warnings[0]["category"] == "limit_reached"
    assert "file limit" in warnings[0]["reason"]


def test_recognized_cloud_file_is_included(tmp_path, monkeypatch):
    from app.tools import file_scanner

    file = tmp_path / "cloud_file.txt"
    file.write_text("NEUROCORE")

    monkeypatch.setattr(
        file_scanner,
        "is_reparse_point",
        lambda path: os.fspath(path) == str(file),
    )
    monkeypatch.setattr(
        file_scanner,
        "is_allowed_cloud_file",
        lambda path: os.fspath(path) == str(file),
    )

    files, warnings = scan_directory(str(tmp_path))

    assert len(files) == 1
    assert files[0]["name"] == "cloud_file.txt"
    assert warnings == []


def test_unsupported_reparse_file_is_skipped(tmp_path, monkeypatch):
    from app.tools import file_scanner

    file = tmp_path / "unsupported.txt"
    file.write_text("NEUROCORE")

    monkeypatch.setattr(
        file_scanner,
        "is_reparse_point",
        lambda path: os.fspath(path) == str(file),
    )
    monkeypatch.setattr(
        file_scanner,
        "is_allowed_cloud_file",
        lambda path: False,
    )

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert warnings == []

def test_file_disappears_during_metadata_inspection(tmp_path, monkeypatch):
    from app.tools import file_scanner

    class FakeEntry:
        path = str(tmp_path / "vanished.txt")
        name = "vanished.txt"

        def is_symlink(self):
            return False

        def is_dir(self, follow_symlinks=False):
            return False

        def is_file(self, follow_symlinks=False):
            return True

        def stat(self, follow_symlinks=False):
            raise FileNotFoundError("File disappeared")

    class FakeScandir:
        def __enter__(self):
            return iter([FakeEntry()])

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(file_scanner, "is_reparse_point", lambda path: False)
    monkeypatch.setattr(file_scanner.os, "scandir", lambda path: FakeScandir())

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert len(warnings) == 1
    assert warnings[0]["category"] == "missing"


def test_directory_disappears_before_traversal(tmp_path, monkeypatch):
    from app.tools import file_scanner

    monkeypatch.setattr(file_scanner, "is_reparse_point", lambda path: False)

    def failing_scandir(path):
        raise FileNotFoundError("Directory disappeared")

    monkeypatch.setattr(file_scanner.os, "scandir", failing_scandir)

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert len(warnings) == 1
    assert warnings[0]["category"] == "missing"

def test_recognized_cloud_directory_is_skipped(tmp_path, monkeypatch):
    from app.tools import file_scanner

    cloud_dir = tmp_path / "cloud_folder"
    cloud_dir.mkdir()
    (cloud_dir / "inside.txt").write_text("NEUROCORE")

    monkeypatch.setattr(
        file_scanner,
        "is_reparse_point",
        lambda path: os.fspath(path) == str(cloud_dir),
    )
    monkeypatch.setattr(
        file_scanner,
        "is_allowed_cloud_directory",
        lambda path: os.fspath(path) == str(cloud_dir),
    )

    files, warnings = scan_directory(str(tmp_path))

    assert files == []
    assert warnings == []
