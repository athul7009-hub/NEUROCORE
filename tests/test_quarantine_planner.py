
import pytest
from uuid import uuid4

from app.core.config import settings
from app.core.schemas import OperationAction
from app.core.operation_planner import (
    create_quarantine_plan,
    create_restore_plan,
)
from app.tools.quarantine_manager import (
    QuarantineMetadata,
    generate_quarantine_paths,
    save_quarantine_metadata,
)


@pytest.fixture
def approved_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(tmp_path)],
    )
    return tmp_path


def test_creates_quarantine_plan(approved_directory):
    source = approved_directory / "report.txt"
    source.write_text("NEUROCORE test")

    plan = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved_directory),
    )

    assert plan.action == OperationAction.QUARANTINE
    assert plan.source_path == str(source)
    assert plan.approved_root == str(approved_directory)
    assert plan.dry_run is True
    assert plan.requires_approval is True
    assert source.exists()


def test_rejects_source_outside_approved_root(approved_directory, tmp_path):
    outside = tmp_path.parent / f"outside_{uuid4().hex}.txt"
    outside.write_text("Outside")

    try:
        with pytest.raises(ValueError):
            create_quarantine_plan(
                task_id=uuid4(),
                source_path=str(outside),
                approved_root=str(approved_directory),
            )
    finally:
        outside.unlink(missing_ok=True)


def test_creates_restore_plan(approved_directory):
    original = approved_directory / "report.txt"
    original.write_text("NEUROCORE test")

    operation_id = uuid4()

    quarantine_file, _ = generate_quarantine_paths(
        str(approved_directory),
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

    save_quarantine_metadata(str(approved_directory), metadata)
    original.rename(quarantine_file)

    plan = create_restore_plan(
        task_id=uuid4(),
        quarantine_operation_id=operation_id,
        approved_root=str(approved_directory),
    )

    assert plan.action == OperationAction.RESTORE
    assert plan.source_path == str(quarantine_file)
    assert plan.destination_path == str(original)
    assert plan.related_operation_id == operation_id
    assert plan.dry_run is True
    assert plan.requires_approval is True


def test_rejects_restore_when_original_file_exists(approved_directory):
    original = approved_directory / "report.txt"
    original.write_text("Original")

    operation_id = uuid4()

    quarantine_file, _ = generate_quarantine_paths(
        str(approved_directory),
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

    save_quarantine_metadata(str(approved_directory), metadata)

    original.rename(quarantine_file)
    original.write_text("Another file")

    with pytest.raises(ValueError):
        create_restore_plan(
            task_id=uuid4(),
            quarantine_operation_id=operation_id,
            approved_root=str(approved_directory),
        )
