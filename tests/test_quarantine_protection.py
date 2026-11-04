
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.approval_manager import ApprovalManager
from app.core.operation_executor import OperationExecutor
from app.core.operation_planner import create_operation_plan
from app.core.schemas import OperationAction, OperationPlan


@pytest.fixture
def protection_setup(tmp_path, monkeypatch):
    approved = tmp_path / "approved"
    approved.mkdir()

    monkeypatch.setattr(
        settings,
        "allowed_scan_roots",
        [str(approved)],
    )

    quarantine = approved / ".neurocore_quarantine"
    files = quarantine / "files"
    files.mkdir(parents=True)

    source = files / "protected.txt"
    source.write_text("Protected quarantine data")

    destination = approved / "destination.txt"

    return approved, quarantine, source, destination


def test_planner_rejects_quarantine_destination(protection_setup):
    approved, quarantine, source, destination = protection_setup

    with pytest.raises(ValueError, match="cannot access quarantine"):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.CREATE,
            destination_path=str(quarantine / "new.txt"),
        )


def test_planner_rejects_quarantine_source(protection_setup):
    approved, quarantine, source, destination = protection_setup

    with pytest.raises(ValueError, match="cannot access quarantine"):
        create_operation_plan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            source_path=str(source),
            destination_path=str(destination),
        )


def test_executor_rejects_quarantine_source(protection_setup):
    approved, quarantine, source, destination = protection_setup

    manager = ApprovalManager()
    executor = OperationExecutor(manager)

    # Deliberately bypass the planner.
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.COPY,
        source_path=str(source),
        destination_path=str(destination),
        dry_run=False,
    )

    manager.register(operation)
    manager.approve(operation.operation_id)

    with pytest.raises(ValueError, match="cannot access quarantine"):
        executor.validate_execution(operation.operation_id)


def test_executor_rejects_quarantine_destination(protection_setup):
    approved, quarantine, source, destination = protection_setup

    manager = ApprovalManager()
    executor = OperationExecutor(manager)

    # Deliberately bypass the planner.
    operation = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.CREATE,
        destination_path=str(quarantine / "new.txt"),
        dry_run=False,
    )

    manager.register(operation)
    manager.approve(operation.operation_id)

    with pytest.raises(ValueError, match="cannot access quarantine"):
        executor.validate_execution(operation.operation_id)
