from uuid import uuid4

import pytest

from app.core.schemas import (
    OperationAction,
    OperationPlan,
    OperationStatus,
)
from app.core.approval_manager import ApprovalManager


@pytest.fixture
def manager():
    return ApprovalManager()


@pytest.fixture
def operation():
    return OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path="old.txt",
        destination_path="new.txt",
    )


def test_register_operation(manager, operation):
    manager.register(operation)

    assert operation.operation_id in manager.pending


def test_approve_operation(manager, operation):
    manager.register(operation)

    manager.approve(operation.operation_id)

    assert operation.status == OperationStatus.APPROVED


def test_reject_operation(manager, operation):
    manager.register(operation)

    manager.reject(operation.operation_id)

    assert operation.status == OperationStatus.REJECTED


def test_rejected_operation_cannot_be_approved(manager, operation):
    manager.register(operation)
    manager.reject(operation.operation_id)

    with pytest.raises(ValueError):
        manager.approve(operation.operation_id)


def test_unregistered_operation_cannot_be_approved(manager):
    with pytest.raises(ValueError):
        manager.approve(uuid4())


def test_only_approved_operations_are_authorized(manager, operation):
    manager.register(operation)

    assert manager.is_authorized(operation.operation_id) is False

    manager.approve(operation.operation_id)

    assert manager.is_authorized(operation.operation_id) is True

def test_approved_operation_is_authorized(manager, operation):
    manager.register(operation)
    manager.approve(operation.operation_id)

    assert manager.is_authorized(operation.operation_id) is True


def test_modified_operation_is_not_authorized(manager, operation):
    manager.register(operation)
    manager.approve(operation.operation_id)

    operation.destination_path = "different.txt"

    assert manager.is_authorized(operation.operation_id) is False


def test_modified_action_is_not_authorized(manager, operation):
    manager.register(operation)
    manager.approve(operation.operation_id)

    operation.action = OperationAction.COPY

    assert manager.is_authorized(operation.operation_id) is False