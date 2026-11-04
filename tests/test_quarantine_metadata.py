
import pytest
from uuid import uuid4

from app.core.config import settings
from app.tools.quarantine_manager import (
    QuarantineMetadata,
    generate_quarantine_paths,
    save_quarantine_metadata,
    load_quarantine_metadata,
    update_quarantine_metadata,
)


@pytest.fixture
def quarantine_setup(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(tmp_path)],
    )

    original = tmp_path / "report.txt"
    original.write_text("NEUROCORE test file")

    operation_id = uuid4()

    quarantine_file, _ = generate_quarantine_paths(
        str(tmp_path),
        operation_id,
        original.name,
    )

    metadata = QuarantineMetadata(
        operation_id=operation_id,
        original_path=str(original),
        quarantine_path=str(quarantine_file),
        original_filename=original.name,
        file_size=original.stat().st_size,
    )

    return tmp_path, metadata


def test_saves_quarantine_metadata(quarantine_setup):
    root, metadata = quarantine_setup

    result = save_quarantine_metadata(str(root), metadata)

    assert result.is_file()


def test_loads_quarantine_metadata(quarantine_setup):
    root, metadata = quarantine_setup

    save_quarantine_metadata(str(root), metadata)

    loaded = load_quarantine_metadata(
        str(root),
        metadata.operation_id,
    )

    assert loaded.operation_id == metadata.operation_id
    assert loaded.original_path == metadata.original_path
    assert loaded.status == "quarantined"


def test_updates_metadata_status(quarantine_setup):
    root, metadata = quarantine_setup

    save_quarantine_metadata(str(root), metadata)

    update_quarantine_metadata(
        str(root),
        metadata.operation_id,
        "restored",
    )

    loaded = load_quarantine_metadata(
        str(root),
        metadata.operation_id,
    )

    assert loaded.status == "restored"


def test_rejects_duplicate_metadata(quarantine_setup):
    root, metadata = quarantine_setup

    save_quarantine_metadata(str(root), metadata)

    with pytest.raises(ValueError):
        save_quarantine_metadata(str(root), metadata)


def test_rejects_missing_metadata(quarantine_setup):
    root, metadata = quarantine_setup

    with pytest.raises(ValueError):
        load_quarantine_metadata(
            str(root),
            metadata.operation_id,
        )


def test_rejects_invalid_metadata_status(quarantine_setup):
    root, metadata = quarantine_setup

    with pytest.raises(ValueError):
        update_quarantine_metadata(
            str(root),
            metadata.operation_id,
            "deleted",
        )

def test_rejects_metadata_with_original_path_outside_root(
    quarantine_setup
):
    root, metadata = quarantine_setup

    save_quarantine_metadata(str(root), metadata)

    metadata_path = (
        root
        / ".neurocore_quarantine"
        / "metadata"
        / f"{metadata.operation_id}.json"
    )

    import json

    data = json.loads(metadata_path.read_text())

    # Simulate metadata tampering.
    data["original_path"] = str(root.parent / "outside.txt")

    metadata_path.write_text(json.dumps(data))

    with pytest.raises(ValueError):
        load_quarantine_metadata(
            str(root),
            metadata.operation_id,
        )
