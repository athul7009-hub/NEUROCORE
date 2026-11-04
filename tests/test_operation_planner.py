
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.operation_planner import (
    create_operation_plan,
    create_rollback_plan,
)

from app.core.schemas import (
    OperationAction,
    OperationPlan,
    OperationStatus,
)


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


def test_create_operation_plan(approved_directory):
    destination = approved_directory / "new_file.txt"

    plan = create_operation_plan(
        task_id=uuid4(),
        action=OperationAction.CREATE,
        destination_path=str(destination),
    )

    assert plan.action == OperationAction.CREATE
    assert plan.status == OperationStatus.PROPOSED
    assert plan.dry_run is True
    assert plan.requires_approval is True
    assert plan.source_path is None


def test_copy_operation_plan(approved_directory):
    source = approved_directory / "source.txt"
    source.write_text("test")

    destination = approved_directory / "copy.txt"

    plan = create_operation_plan(
        task_id=uuid4(),
        action=OperationAction.COPY,
        source_path=str(source),
        destination_path=str(destination),
    )

    assert plan.action == OperationAction.COPY
    assert plan.source_path == str(source)
    assert plan.destination_path == str(destination)


def test_rename_operation_plan(approved_directory):
    source = approved_directory / "old.txt"
    source.write_text("test")

    destination = approved_directory / "new.txt"

    plan = create_operation_plan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path=str(source),
        destination_path=str(destination),
    )

    assert plan.action == OperationAction.RENAME


def test_rejects_copy_without_source(approved_directory):
    with pytest.raises(ValueError):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            destination_path=str(approved_directory / "copy.txt"),
        )


def test_rejects_create_with_source(approved_directory):
    with pytest.raises(ValueError):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.CREATE,
            source_path="unexpected.txt",
            destination_path=str(approved_directory / "new.txt"),
        )


def test_rejects_missing_source(approved_directory):
    with pytest.raises(ValueError):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            source_path=str(approved_directory / "missing.txt"),
            destination_path=str(approved_directory / "copy.txt"),
        )


def test_rejects_existing_destination(approved_directory):
    source = approved_directory / "source.txt"
    source.write_text("test")

    destination = approved_directory / "existing.txt"
    destination.write_text("already exists")

    with pytest.raises(ValueError):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            source_path=str(source),
            destination_path=str(destination),
        )


def test_rejects_directory_as_source(approved_directory):
    source_directory = approved_directory / "folder"
    source_directory.mkdir()

    with pytest.raises(ValueError):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            source_path=str(source_directory),
            destination_path=str(approved_directory / "copy.txt"),
        )


def test_creates_valid_rename_rollback_plan(approved_directory):
    original = approved_directory / "old.txt"
    renamed = approved_directory / "new.txt"

    renamed.write_text("NEUROCORE rollback test")

    completed_operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path=str(original),
        destination_path=str(renamed),
        status=OperationStatus.EXECUTED,
        dry_run=False,
        rollback_data={
            "original_path": str(original),
            "renamed_path": str(renamed),
        },
    )

    rollback = create_rollback_plan(completed_operation)

    assert rollback.action == OperationAction.RENAME
    assert rollback.source_path == str(renamed)
    assert rollback.destination_path == str(original)
    assert rollback.status == OperationStatus.PROPOSED
    assert rollback.dry_run is True
    assert rollback.requires_approval is True
    assert rollback.operation_id != completed_operation.operation_id


def test_rejects_rollback_for_unexecuted_operation():
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path="C:/test/old.txt",
        destination_path="C:/test/new.txt",
        status=OperationStatus.PROPOSED,
    )

    with pytest.raises(ValueError, match="successfully executed"):
        create_rollback_plan(operation)


def test_rejects_rollback_for_copy_operation():
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.COPY,
        source_path="C:/test/source.txt",
        destination_path="C:/test/copy.txt",
        status=OperationStatus.EXECUTED,
    )

    with pytest.raises(ValueError, match="only for RENAME"):
        create_rollback_plan(operation)


def test_rejects_missing_rollback_information():
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path="C:/test/old.txt",
        destination_path="C:/test/new.txt",
        status=OperationStatus.EXECUTED,
    )

    with pytest.raises(ValueError, match="incomplete"):
        create_rollback_plan(operation)


def test_rejects_mismatched_rollback_information():
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path="C:/test/old.txt",
        destination_path="C:/test/new.txt",
        status=OperationStatus.EXECUTED,
        rollback_data={
            "original_path": "C:/test/another.txt",
            "renamed_path": "C:/test/new.txt",
        },
    )

    with pytest.raises(ValueError, match="Original source"):
        create_rollback_plan(operation)
