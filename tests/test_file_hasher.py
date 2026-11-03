
from app.tools.file_hasher import calculate_hash
import pytest
from app.tools.file_hasher import calculate_hash, MAX_HASH_SIZE_BYTES


def test_identical_files_have_same_hash(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    first.write_text("NEUROCORE")
    second.write_text("NEUROCORE")

    assert calculate_hash(str(first)) == calculate_hash(str(second))


def test_different_files_have_different_hashes(tmp_path):
    first = tmp_path / "first.txt"
    second = tmp_path / "second.txt"

    first.write_text("NEUROCORE")
    second.write_text("Different content")

    assert calculate_hash(str(first)) != calculate_hash(str(second))


def test_empty_file_hash(tmp_path):
    file = tmp_path / "empty.txt"
    file.touch()

    assert len(calculate_hash(str(file))) == 64


def test_hash_size_limit(tmp_path, monkeypatch):
    file = tmp_path / "large.txt"
    file.write_bytes(b"x" * 11)

    monkeypatch.setattr(
        "app.tools.file_hasher.MAX_HASH_SIZE_BYTES", 10
    )

    with pytest.raises(ValueError, match="100 MB hashing limit"):
        calculate_hash(str(file))


def test_missing_file():
    with pytest.raises(OSError):
        calculate_hash("missing_file.txt")
