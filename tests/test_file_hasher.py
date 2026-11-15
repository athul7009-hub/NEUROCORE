
import pytest

from app.tools.file_hasher import calculate_hash


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

    with pytest.raises(ValueError, match="configured hashing size limit"):
        calculate_hash(str(file))


def test_missing_file():
    with pytest.raises(OSError):
        calculate_hash("missing_file.txt")
def test_symlink_file_is_rejected(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("NEUROCORE")

    link = tmp_path / "linked.txt"

    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic-link creation is unavailable.")

    from app.tools.file_hasher import UnsafeFileError

    with pytest.raises(UnsafeFileError):
        calculate_hash(str(link))
def test_symlinked_parent_directory_is_rejected(tmp_path):
    from app.tools.file_hasher import UnsafeFileError

    external = tmp_path / "external"
    external.mkdir()

    secret = external / "secret.txt"
    secret.write_text("Private data")

    approved = tmp_path / "approved"
    approved.mkdir()

    link = approved / "linked_folder"

    try:
        link.symlink_to(external, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Symbolic-link creation is unavailable.")

    with pytest.raises(UnsafeFileError):
        calculate_hash(str(link / "secret.txt"))

from app.tools.file_hasher import UnsafeFileError


def test_hash_file_inside_approved_root(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()

    file = approved / "document.txt"
    file.write_text("NEUROCORE")

    result = calculate_hash(
        str(file),
        allowed_root=approved,
    )

    assert len(result) == 64


def test_hash_file_outside_approved_root_rejected(tmp_path):
    approved = tmp_path / "approved"
    approved.mkdir()

    external = tmp_path / "external"
    external.mkdir()

    file = external / "secret.txt"
    file.write_text("Private data")

    with pytest.raises(UnsafeFileError, match="outside"):
        calculate_hash(
            str(file),
            allowed_root=approved,
        )


def test_directory_cannot_be_hashed(tmp_path):
    directory = tmp_path / "folder"
    directory.mkdir()

    with pytest.raises(UnsafeFileError):
        calculate_hash(str(directory))


def test_opened_windows_path_must_be_inside_root(tmp_path):
    from app.tools.file_hasher import (
        _ensure_windows_path_within_root,
    )

    approved = tmp_path / "approved"
    approved.mkdir()

    external = tmp_path / "external"
    external.mkdir()

    with pytest.raises(UnsafeFileError):
        _ensure_windows_path_within_root(
            str(external / "secret.txt"),
            approved,
        )
