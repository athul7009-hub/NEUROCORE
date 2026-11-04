
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.approval_manager import ApprovalManager
from app.core.operation_executor import OperationExecutor
from app.core.operation_planner import (
    create_quarantine_plan,
    create_restore_plan,
)
from app.core.schemas import OperationStatus
from app.tools.quarantine_manager import load_quarantine_metadata


@pytest.fixture
def setup_quarantine(tmp_path, monkeypatch):
    approved = tmp_path / "approved"
    approved.mkdir()

    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(approved)],
    )

    manager = ApprovalManager()
    executor = OperationExecutor(manager)

    source = approved / "important.txt"
    source.write_text("NEUROCORE quarantine execution test")

    return manager, executor, approved, source


def test_executes_approved_quarantine(setup_quarantine):
    manager, executor, approved, source = setup_quarantine

    # Create quarantine plan.
    operation = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )

    operation.dry_run = False

    manager.register(operation)
    manager.approve(operation.operation_id)

    # Execute quarantine.
    result = executor.execute(operation.operation_id)

    # Verify file movement.
    assert result.exists()
    assert result.is_file()
    assert not source.exists()
    assert result.read_text() == "NEUROCORE quarantine execution test"

    # Verify metadata.
    metadata = load_quarantine_metadata(
        str(approved),
        operation.operation_id,
    )

    assert metadata.original_path == str(source)
    assert metadata.quarantine_path == str(result)
    assert metadata.original_filename == "important.txt"
    assert metadata.file_size == len(
        "NEUROCORE quarantine execution test"
    )
    assert metadata.status == "quarantined"

    assert operation.status == OperationStatus.EXECUTED


def test_executes_approved_restore(setup_quarantine):
    manager, executor, approved, source = setup_quarantine

    # Step 1: Quarantine the file.
    quarantine = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )

    quarantine.dry_run = False

    manager.register(quarantine)
    manager.approve(quarantine.operation_id)

    quarantine_path = executor.execute(quarantine.operation_id)

    # Step 2: Create an independent restore plan.
    restore = create_restore_plan(
        task_id=uuid4(),
        quarantine_operation_id=quarantine.operation_id,
        approved_root=str(approved),
    )

    restore.dry_run = False

    manager.register(restore)
    manager.approve(restore.operation_id)

    # Step 3: Execute restoration.
    result = executor.execute(restore.operation_id)

    # Step 4: Verify restoration.
    assert result == source
    assert source.exists()
    assert not quarantine_path.exists()
    assert source.read_text() == "NEUROCORE quarantine execution test"

    # Verify metadata.
    metadata = load_quarantine_metadata(
        str(approved),
        quarantine.operation_id,
    )

    assert metadata.status == "restored"
    assert restore.status == OperationStatus.EXECUTED


def test_quarantine_recovers_when_metadata_save_fails(
    setup_quarantine, monkeypatch
):
    manager, executor, approved, source = setup_quarantine

    operation = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )

    operation.dry_run = False

    manager.register(operation)
    manager.approve(operation.operation_id)

    # Simulate metadata persistence failure.
    def simulate_metadata_failure(*args, **kwargs):
        raise OSError("Simulated metadata save failure")

    monkeypatch.setattr(
        "app.core.operation_executor.save_quarantine_metadata",
        simulate_metadata_failure,
    )

    # Executor should report successful recovery.
    with pytest.raises(
        RuntimeError,
        match="file was returned to its original location",
    ):
        executor.execute(operation.operation_id)

    # Verify original file was recovered.
    assert source.exists()
    assert source.read_text() == "NEUROCORE quarantine execution test"

    # Verify quarantine destination is empty.
    assert not Path(operation.destination_path).exists()

    # Verify operation status.
    assert operation.status == OperationStatus.FAILED

def test_reports_failure_when_quarantine_recovery_fails(
    setup_quarantine, monkeypatch
):
    manager, executor, approved, source = setup_quarantine

    operation = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )
    operation.dry_run = False

    manager.register(operation)
    manager.approve(operation.operation_id)

    original_rename = __import__(
        "os"
    ).rename

    def simulate_recovery_failure(src, dst):
        if Path(src) == Path(operation.destination_path):
            raise OSError("Simulated recovery failure")

        original_rename(src, dst)

    monkeypatch.setattr(
        "app.core.operation_executor.os.rename",
        simulate_recovery_failure,
    )

    monkeypatch.setattr(
        "app.core.operation_executor.save_quarantine_metadata",
        lambda *args, **kwargs: (
            (_ for _ in ()).throw(
                OSError("Simulated metadata save failure")
            )
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="automatic recovery also failed",
    ):
        executor.execute(operation.operation_id)

    # The original file may remain in quarantine.
    assert not source.exists()
    assert Path(operation.destination_path).exists()

    assert operation.status == OperationStatus.FAILED

def test_restore_recovers_when_metadata_update_fails(
    setup_quarantine, monkeypatch
):
    manager, executor, approved, source = setup_quarantine

    # Step 1: Quarantine the file successfully.
    quarantine = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )
    quarantine.dry_run = False

    manager.register(quarantine)
    manager.approve(quarantine.operation_id)

    quarantine_path = executor.execute(quarantine.operation_id)

    # Step 2: Create and approve a separate restore plan.
    restore = create_restore_plan(
        task_id=uuid4(),
        quarantine_operation_id=quarantine.operation_id,
        approved_root=str(approved),
    )
    restore.dry_run = False

    manager.register(restore)
    manager.approve(restore.operation_id)

    # Step 3: Simulate metadata update failure.
    def simulate_metadata_failure(*args, **kwargs):
        raise OSError("Simulated metadata update failure")

    monkeypatch.setattr(
        "app.core.operation_executor.update_quarantine_metadata",
        simulate_metadata_failure,
    )

    # Step 4: Execute restoration and expect recovery.
    with pytest.raises(RuntimeError):
        executor.execute(restore.operation_id)

    # Step 5: Verify the file returned to quarantine.
    assert not source.exists()
    assert quarantine_path.exists()
    assert quarantine_path.read_text() == (
        "NEUROCORE quarantine execution test"
    )

    # Metadata should still report quarantined.
    metadata = load_quarantine_metadata(
        str(approved),
        quarantine.operation_id,
    )
    assert metadata.status == "quarantined"

    assert restore.status == OperationStatus.FAILED

def test_quarantine_recovers_when_movement_verification_fails(
    setup_quarantine, monkeypatch
):
    manager, executor, approved, source = setup_quarantine

    operation = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )
    operation.dry_run = False

    manager.register(operation)
    manager.approve(operation.operation_id)

    original_is_file = Path.is_file
    destination = Path(operation.destination_path)

    def simulate_verification_failure(path):
        if path == destination:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", simulate_verification_failure)

    with pytest.raises(ValueError, match="Quarantine movement verification failed"):
        executor.execute(operation.operation_id)

    # The file should be recovered to its original location.
    assert source.exists()
    assert source.read_text() == "NEUROCORE quarantine execution test"

    # No file should remain in quarantine.
    assert not destination.exists()

    assert operation.status == OperationStatus.FAILED

def test_restore_recovers_when_movement_verification_fails(
    setup_quarantine, monkeypatch
):
    manager, executor, approved, source = setup_quarantine

    # First quarantine the file.
    quarantine = create_quarantine_plan(
        task_id=uuid4(),
        source_path=str(source),
        approved_root=str(approved),
    )
    quarantine.dry_run = False

    manager.register(quarantine)
    manager.approve(quarantine.operation_id)

    quarantine_path = executor.execute(quarantine.operation_id)

    # Create and approve an independent restore operation.
    restore = create_restore_plan(
        task_id=uuid4(),
        quarantine_operation_id=quarantine.operation_id,
        approved_root=str(approved),
    )
    restore.dry_run = False

    manager.register(restore)
    manager.approve(restore.operation_id)

    original_is_file = Path.is_file

    def simulate_verification_failure(path):
        if path == source:
            return False
        return original_is_file(path)

    monkeypatch.setattr(Path, "is_file", simulate_verification_failure)

    with pytest.raises(ValueError, match="Restore movement verification failed"):
        executor.execute(restore.operation_id)

    # File should return to quarantine.
    assert not source.exists()
    assert quarantine_path.exists()
    assert quarantine_path.read_text() == (
        "NEUROCORE quarantine execution test"
    )

    # Metadata must remain unchanged.
    metadata = load_quarantine_metadata(
        str(approved),
        quarantine.operation_id,
    )
    assert metadata.status == "quarantined"

    assert restore.status == OperationStatus.FAILED
