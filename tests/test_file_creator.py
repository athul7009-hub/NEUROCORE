
import pytest

from app.core.config import settings
from app.tools.file_creator import create_empty_file


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


def test_creates_empty_file(approved_directory):
    destination = approved_directory / "new.txt"

    result = create_empty_file(str(destination))

    assert result.exists()
    assert result.is_file()
    assert result.stat().st_size == 0


def test_rejects_existing_file(approved_directory):
    destination = approved_directory / "existing.txt"
    destination.write_text("original content")

    with pytest.raises(ValueError, match="already exists"):
        create_empty_file(str(destination))

    assert destination.read_text() == "original content"


def test_rejects_path_outside_approved_directory(
    approved_directory, tmp_path
):
    destination = tmp_path / "outside.txt"

    with pytest.raises(ValueError, match="outside approved"):
        create_empty_file(str(destination))

    assert not destination.exists()


def test_rejects_missing_parent_directory(approved_directory):
    destination = approved_directory / "missing" / "new.txt"

    with pytest.raises(ValueError):
        create_empty_file(str(destination))

    assert not destination.parent.exists()


def test_creates_file_inside_subdirectory(approved_directory):
    subdirectory = approved_directory / "documents"
    subdirectory.mkdir()

    destination = subdirectory / "notes.txt"

    result = create_empty_file(str(destination))

    assert result.exists()
    assert result.stat().st_size == 0
