
import pytest
from uuid import uuid4

from app.core.config import settings
from app.tools.quarantine_manager import (
    ensure_quarantine_storage,
    generate_quarantine_paths,
)


@pytest.fixture
def approved_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(tmp_path)],
    )
    return tmp_path


def test_creates_quarantine_directory_structure(approved_directory):
    files_dir, metadata_dir = ensure_quarantine_storage(
        str(approved_directory)
    )

    assert files_dir.is_dir()
    assert metadata_dir.is_dir()

    assert files_dir.name == "files"
    assert metadata_dir.name == "metadata"
    assert files_dir.parent.name == ".neurocore_quarantine"


def test_generates_unique_quarantine_paths(approved_directory):
    operation_one = uuid4()
    operation_two = uuid4()

    file_one, metadata_one = generate_quarantine_paths(
        str(approved_directory),
        operation_one,
        "report.txt",
    )

    file_two, metadata_two = generate_quarantine_paths(
        str(approved_directory),
        operation_two,
        "report.txt",
    )

    assert file_one != file_two
    assert metadata_one != metadata_two


def test_rejects_invalid_filename(approved_directory):
    with pytest.raises(ValueError):
        generate_quarantine_paths(
            str(approved_directory),
            uuid4(),
            "",
        )


def test_rejects_file_at_quarantine_directory_path(approved_directory):
    quarantine_root = (
        approved_directory / ".neurocore_quarantine"
    )

    quarantine_root.write_text("Not a directory")

    with pytest.raises(ValueError):
        ensure_quarantine_storage(str(approved_directory))
