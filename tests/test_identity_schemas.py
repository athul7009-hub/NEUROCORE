
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
    MemoryIdentityRequest,
)
from app.memory.meta_schemas import MetaMemoryType


def test_all_memory_types_are_supported():
    for memory_type in MetaMemoryType:
        data = {
            "memory_type": memory_type,
            "memory_id": uuid4(),
        }

        if memory_type == MetaMemoryType.WORKING:
            data["task_id"] = uuid4()

        request = MemoryIdentityRequest(**data)

        assert request.memory_type == memory_type


def test_working_memory_requires_task_id():
    with pytest.raises(ValidationError):
        MemoryIdentityRequest(
            memory_type=MetaMemoryType.WORKING,
            memory_id=uuid4(),
        )


def test_non_working_memory_rejects_task_id():
    with pytest.raises(ValidationError):
        MemoryIdentityRequest(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            task_id=uuid4(),
        )


def test_identity_request_is_immutable():
    request = MemoryIdentityRequest(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=uuid4(),
    )

    with pytest.raises(ValidationError):
        request.memory_id = uuid4()


def test_not_found_assessment_is_valid():
    assessment = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=uuid4(),
        exists=False,
        availability=MemoryIdentityAvailability.NOT_FOUND,
    )

    assert not assessment.exists
    assert assessment.lifecycle_status is None


def test_not_found_cannot_indicate_existing_memory():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            exists=True,
            availability=MemoryIdentityAvailability.NOT_FOUND,
        )


def test_not_found_cannot_have_lifecycle_status():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            exists=False,
            lifecycle_status="validated",
            availability=MemoryIdentityAvailability.NOT_FOUND,
        )


def test_existing_assessment_requires_exists_true():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            exists=False,
            availability=MemoryIdentityAvailability.AVAILABLE,
        )


def test_working_assessment_requires_task_id():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.WORKING,
            memory_id=uuid4(),
            exists=True,
            lifecycle_status="active",
            availability=MemoryIdentityAvailability.AVAILABLE,
        )


def test_working_assessment_accepts_task_id():
    task_id = uuid4()

    assessment = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.WORKING,
        memory_id=uuid4(),
        task_id=task_id,
        exists=True,
        lifecycle_status="active",
        availability=MemoryIdentityAvailability.AVAILABLE,
    )

    assert assessment.task_id == task_id


def test_non_working_assessment_rejects_task_id():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            task_id=uuid4(),
            exists=True,
            lifecycle_status="validated",
            availability=MemoryIdentityAvailability.AVAILABLE,
        )


def test_assessment_is_immutable():
    assessment = MemoryIdentityAssessment(
        memory_type=MetaMemoryType.SEMANTIC,
        memory_id=uuid4(),
        exists=True,
        lifecycle_status="validated",
        availability=MemoryIdentityAvailability.AVAILABLE,
    )

    with pytest.raises(ValidationError):
        assessment.exists = False


def test_lifecycle_status_maximum_length():
    with pytest.raises(ValidationError):
        MemoryIdentityAssessment(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            exists=True,
            lifecycle_status="x" * 51,
            availability=MemoryIdentityAvailability.AVAILABLE,
        )


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        MemoryIdentityRequest(
            memory_type=MetaMemoryType.SEMANTIC,
            memory_id=uuid4(),
            unexpected_field="value",
        )
