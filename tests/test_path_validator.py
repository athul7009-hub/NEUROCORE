import pytest

from app.core.config import settings
from app.core.path_validator import validate_path


@pytest.fixture
def approved_directory(tmp_path, monkeypatch):
    approved = tmp_path / "approved"
    approved.mkdir()

    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(approved)],
    )

    return approved


def test_accepts_path_inside_approved_directory(approved_directory):
    target = approved_directory / "document.txt"
    target.write_text("test")

    result = validate_path(str(target), must_exist=True)

    assert result == target


def test_accepts_approved_root(approved_directory):
    result = validate_path(str(approved_directory), must_exist=True)

    assert result == approved_directory


def test_rejects_path_outside_approved_directory(approved_directory, tmp_path):
    outside = tmp_path / "outside.txt"

    with pytest.raises(ValueError):
        validate_path(str(outside))


def test_rejects_relative_path():
    with pytest.raises(ValueError):
        validate_path("documents/test.txt")


def test_rejects_directory_traversal(approved_directory, tmp_path):
    outside = tmp_path / "outside.txt"
    traversal_path = approved_directory / ".." / outside.name

    with pytest.raises(ValueError):
        validate_path(str(traversal_path))


def test_rejects_missing_path_when_required(approved_directory):
    missing = approved_directory / "missing.txt"

    with pytest.raises(ValueError):
        validate_path(str(missing), must_exist=True)


def test_rejects_path_when_no_approved_roots(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "allowed_scan_roots", [])

    with pytest.raises(ValueError):
        validate_path(str(tmp_path / "test.txt"))