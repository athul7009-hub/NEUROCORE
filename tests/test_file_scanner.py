
import pytest

from app.tools.file_scanner import scan_directory


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

    with pytest.raises(ValueError, match="Scan limit exceeded"):
        scan_directory(str(tmp_path), max_files=1)
