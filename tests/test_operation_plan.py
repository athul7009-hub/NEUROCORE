from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.schemas import (
    OperationAction,
    OperationPlan,
    OperationStatus,
)


def test_operation_plan_defaults():
    plan = OperationPlan(
        task_id=uuid4(),
        action=OperationAction.RENAME,
        source_path="report_old.txt",
        destination_path="report_final.txt",
    )

    assert plan.status == OperationStatus.PROPOSED
    assert plan.dry_run is True
    assert plan.requires_approval is True


def test_operation_plan_has_unique_ids():
    task_id = uuid4()

    plan1 = OperationPlan(
        task_id=task_id,
        action=OperationAction.CREATE,
        destination_path="new_file.txt",
    )

    plan2 = OperationPlan(
        task_id=task_id,
        action=OperationAction.CREATE,
        destination_path="another_file.txt",
    )

    assert plan1.operation_id != plan2.operation_id


def test_invalid_operation_action():
    with pytest.raises(ValidationError):
        OperationPlan(
            task_id=uuid4(),
            action="delete",
            destination_path="file.txt",
        )


def test_operation_plan_rejects_extra_fields():
    with pytest.raises(ValidationError):
        OperationPlan(
            task_id=uuid4(),
            action=OperationAction.COPY,
            destination_path="copy.txt",
            unauthorized=True,
        )