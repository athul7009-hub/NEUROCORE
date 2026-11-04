
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.approval_manager import ApprovalManager
from app.core.operation_executor import OperationExecutor
from app.core.operation_planner import create_rollback_plan
from app.core.schemas import (
    OperationAction,
    OperationPlan,
    OperationStatus,
)


@pytest.fixture
def setup_executor(tmp_path, monkeypatch):
    approved = tmp_path / "approved"
    approved.mkdir()

    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(approved)],
    )

    manager = ApprovalManager()
    executor = OperationExecutor(manager)

    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.CREATE,
        destination_path=str(approved / "test.txt"),
        dry_run=False,
    )

    manager.register(operation)

    return manager, executor, operation, approved


def test_rejects_unapproved_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    with pytest.raises(ValueError, match="not been approved"):
        executor.validate_execution(operation.operation_id)


def test_rejects_modified_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    manager.approve(operation.operation_id)
    operation.destination_path = str(approved / "modified.txt")

    with pytest.raises(ValueError, match="modified"):
        executor.validate_execution(operation.operation_id)


def test_rejects_dry_run_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    operation.dry_run = True
    manager.approve(operation.operation_id)

    with pytest.raises(ValueError, match="dry-run"):
        executor.validate_execution(operation.operation_id)


def test_accepts_approved_unchanged_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    manager.approve(operation.operation_id)

    result = executor.validate_execution(operation.operation_id)

    assert result.operation_id == operation.operation_id


def test_rejects_existing_destination(setup_executor):
    manager, executor, operation, approved = setup_executor

    operation.destination_path = str(approved / "test.txt")
    manager.approve(operation.operation_id)

    (approved / "test.txt").write_text("existing file")

    with pytest.raises(ValueError, match="Destination already exists"):
        executor.validate_execution(operation.operation_id)


def test_rejects_source_outside_approved_directory(setup_executor, tmp_path):
    manager, executor, operation, approved = setup_executor

    outside = tmp_path / "outside.txt"
    outside.write_text("test")

    operation.action = OperationAction.COPY
    operation.source_path = str(outside)
    manager.approve(operation.operation_id)

    with pytest.raises(ValueError, match="outside approved"):
        executor.validate_execution(operation.operation_id)


def test_rejects_missing_source(setup_executor):
    manager, executor, operation, approved = setup_executor

    operation.action = OperationAction.COPY
    operation.source_path = str(approved / "missing.txt")
    manager.approve(operation.operation_id)

    with pytest.raises(ValueError):
        executor.validate_execution(operation.operation_id)


def test_executes_approved_create_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    manager.approve(operation.operation_id)

    result = executor.execute(operation.operation_id)

    assert result.exists()
    assert result.is_file()
    assert result.stat().st_size == 0
    assert operation.status == OperationStatus.EXECUTED

def test_failed_operation_cannot_be_retried(
    setup_executor, monkeypatch
):
    manager, executor, operation, approved = setup_executor

    manager.approve(operation.operation_id)

    def simulate_failure(destination_path):
        raise OSError("Simulated file creation failure")

    monkeypatch.setattr(
        "app.core.operation_executor.create_empty_file",
        simulate_failure,
    )

    with pytest.raises(OSError, match="Simulated file creation failure"):
        executor.execute(operation.operation_id)

    assert operation.status == OperationStatus.FAILED

    with pytest.raises(ValueError, match="not been approved"):
        executor.execute(operation.operation_id)

def test_marks_operation_failed_when_verification_fails(
    setup_executor, monkeypatch
):
    manager, executor, operation, approved = setup_executor

    manager.approve(operation.operation_id)

    fake_file = approved / "fake.txt"

    monkeypatch.setattr(
        "app.core.operation_executor.create_empty_file",
        lambda destination: fake_file,
    )

    with pytest.raises(ValueError, match="verification failed"):
        executor.execute(operation.operation_id)

    assert operation.status == OperationStatus.FAILED
def test_executes_approved_copy_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    source = approved / "source.txt"
    destination = approved / "test.txt"

    source.write_text("NEUROCORE COPY execution test")

    operation.action = OperationAction.COPY
    operation.source_path = str(source)
    operation.destination_path = str(destination)

    manager.approve(operation.operation_id)

    result = executor.execute(operation.operation_id)

    assert result.exists()
    assert result.is_file()
    assert result.read_text() == source.read_text()
    assert operation.status == OperationStatus.EXECUTED

def test_failed_copy_operation_cannot_be_retried(
    setup_executor, monkeypatch
):
    manager, executor, operation, approved = setup_executor

    source = approved / "source.txt"
    source.write_text("COPY failure test")

    operation.action = OperationAction.COPY
    operation.source_path = str(source)

    manager.approve(operation.operation_id)

    def simulate_failure(source_path, destination_path):
        raise OSError("Simulated copy failure")

    monkeypatch.setattr(
        "app.core.operation_executor.copy_file",
        simulate_failure,
    )

    with pytest.raises(OSError, match="Simulated copy failure"):
        executor.execute(operation.operation_id)

    assert operation.status == OperationStatus.FAILED

    with pytest.raises(ValueError, match="not been approved"):
        executor.execute(operation.operation_id)

def test_marks_copy_failed_when_content_verification_fails(
    setup_executor, monkeypatch
):
    manager, executor, operation, approved = setup_executor

    source = approved / "source.txt"
    incorrect_copy = approved / "incorrect.txt"

    source.write_text("Original content")
    incorrect_copy.write_text("Different content")

    operation.action = OperationAction.COPY
    operation.source_path = str(source)

    manager.approve(operation.operation_id)

    monkeypatch.setattr(
        "app.core.operation_executor.copy_file",
        lambda source_path, destination_path: incorrect_copy,
    )

    with pytest.raises(ValueError, match="Copied file verification failed"):
        executor.execute(operation.operation_id)

    assert operation.status == OperationStatus.FAILED


def test_executes_approved_rename_operation(setup_executor):
    manager, executor, operation, approved = setup_executor

    source = approved / "old_name.txt"
    destination = approved / "new_name.txt"

    source.write_text("NEUROCORE RENAME test")

    operation.action = OperationAction.RENAME
    operation.source_path = str(source)
    operation.destination_path = str(destination)

    manager.approve(operation.operation_id)

    result = executor.execute(operation.operation_id)

    # Verify rename execution
    assert result == destination
    assert destination.exists()
    assert destination.is_file()
    assert not source.exists()
    assert destination.read_text() == "NEUROCORE RENAME test"

    # Verify operation status
    assert operation.status == OperationStatus.EXECUTED

    # Verify rollback information
    assert operation.rollback_data["original_path"] == str(source)
    assert operation.rollback_data["renamed_path"] == str(destination)


def test_executes_approved_rename_rollback(setup_executor):
    manager, executor, operation, approved = setup_executor

    source = approved / "old.txt"
    destination = approved / "new.txt"

    original_content = "NEUROCORE rollback verification test"
    source.write_text(original_content)

    # Step 1: Execute original rename
    operation.action = OperationAction.RENAME
    operation.source_path = str(source)
    operation.destination_path = str(destination)

    manager.approve(operation.operation_id)

    result = executor.execute(operation.operation_id)

    assert result == destination
    assert destination.exists()
    assert not source.exists()
    assert operation.status == OperationStatus.EXECUTED

    # Step 2: Generate a new rollback plan
    rollback = create_rollback_plan(operation)

    # Step 3: Enable execution and register independently
    rollback.dry_run = False
    manager.register(rollback)

    # Step 4: Independently approve rollback
    manager.approve(rollback.operation_id)

    # Step 5: Execute rollback
    restored = executor.execute(rollback.operation_id)

    # Step 6: Verify restoration
    assert restored == source
    assert source.exists()
    assert not destination.exists()
    assert source.read_text() == original_content

    assert rollback.status == OperationStatus.EXECUTED
def test_rollback_rejects_existing_original_path(setup_executor):
    manager, executor, operation, approved = setup_executor

    source = approved / "old.txt"
    destination = approved / "new.txt"

    source.write_text("Original content")

    operation.action = OperationAction.RENAME
    operation.source_path = str(source)
    operation.destination_path = str(destination)

    manager.approve(operation.operation_id)
    executor.execute(operation.operation_id)

    # Another file now occupies the original path.
    source.write_text("Do not overwrite this file")

    with pytest.raises(ValueError):
        create_rollback_plan(operation)

    # Both files must remain untouched.
    assert source.read_text() == "Do not overwrite this file"
    assert destination.read_text() == "Original content"

def test_rollback_rejects_missing_renamed_file(setup_executor):
    manager, executor, operation, approved = setup_executor

    source = approved / "old.txt"
    destination = approved / "new.txt"

    source.write_text("Original content")

    operation.action = OperationAction.RENAME
    operation.source_path = str(source)
    operation.destination_path = str(destination)

    manager.approve(operation.operation_id)
    executor.execute(operation.operation_id)

    # Simulate the renamed file being removed externally.
    destination.unlink()

    with pytest.raises(ValueError):
        create_rollback_plan(operation)

    assert not source.exists()
    assert not destination.exists()