
import pytest

from app.core.config import settings
from app.tools.file_copier import copy_file


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


def test_copies_file_successfully(approved_directory):
    source = approved_directory / "source.txt"
    destination = approved_directory / "copy.txt"

    source.write_text("NEUROCORE COPY test")

    result = copy_file(str(source), str(destination))

    assert result.exists()
    assert result.is_file()
    assert result.read_text() == "NEUROCORE COPY test"


def test_rejects_existing_destination(approved_directory):
    source = approved_directory / "source.txt"
    destination = approved_directory / "copy.txt"

    source.write_text("source content")
    destination.write_text("original destination")

    with pytest.raises(ValueError, match="already exists"):
        copy_file(str(source), str(destination))

    assert destination.read_text() == "original destination"


def test_rejects_source_outside_approved_directory(
    approved_directory, tmp_path
):
    source = tmp_path / "outside.txt"
    destination = approved_directory / "copy.txt"

    source.write_text("outside content")

    with pytest.raises(ValueError, match="outside approved"):
        copy_file(str(source), str(destination))

    assert not destination.exists()


def test_rejects_destination_outside_approved_directory(
    approved_directory, tmp_path
):
    source = approved_directory / "source.txt"
    destination = tmp_path / "outside.txt"

    source.write_text("source content")

    with pytest.raises(ValueError, match="outside approved"):
        copy_file(str(source), str(destination))

    assert not destination.exists()


def test_rejects_missing_source(approved_directory):
    source = approved_directory / "missing.txt"
    destination = approved_directory / "copy.txt"

    with pytest.raises(ValueError):
        copy_file(str(source), str(destination))

    assert not destination.exists()


def test_rejects_directory_as_source(approved_directory):
    source = approved_directory / "folder"
    source.mkdir()

    destination = approved_directory / "copy.txt"

    with pytest.raises(ValueError, match="existing file"):
        copy_file(str(source), str(destination))

    assert not destination.exists()

def test_removes_partial_file_when_copy_fails(
    approved_directory, monkeypatch
):
    source = approved_directory / "source.txt"
    destination = approved_directory / "copy.txt"

    source.write_text("NEUROCORE partial copy test")

    original_open = type(source).open

    class FailingReader:
        def __init__(self, file_object):
            self.file_object = file_object

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.file_object.close()

        def read(self, size=-1):
            raise OSError("Simulated read failure")

    def failing_open(path, *args, **kwargs):
        if path == source:
            return FailingReader(original_open(path, *args, **kwargs))

        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(type(source), "open", failing_open)

    with pytest.raises(OSError, match="Simulated read failure"):
        copy_file(str(source), str(destination))

    assert not destination.exists()