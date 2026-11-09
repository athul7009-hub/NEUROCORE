
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.memory.meta_maintenance_schemas import (
    MetaMemoryMaintenanceReport,
)


@pytest.fixture
def valid_report_data():
    now = datetime.now(timezone.utc)

    return {
        "total_examined": 3,
        "assessed": 1,
        "skipped": 1,
        "failed": 1,
        "failed_meta_ids": [uuid4()],
        "started_at": now,
        "completed_at": now + timedelta(seconds=1),
    }


def test_creates_valid_report(valid_report_data):
    report = MetaMemoryMaintenanceReport(**valid_report_data)

    assert report.total_examined == 3
    assert report.assessed == 1
    assert report.skipped == 1
    assert report.failed == 1


def test_rejects_inconsistent_counts(valid_report_data):
    valid_report_data["assessed"] = 2

    with pytest.raises(ValidationError):
        MetaMemoryMaintenanceReport(**valid_report_data)


def test_rejects_mismatched_failed_ids(valid_report_data):
    valid_report_data["failed_meta_ids"] = []

    with pytest.raises(ValidationError):
        MetaMemoryMaintenanceReport(**valid_report_data)


@pytest.mark.parametrize(
    "field",
    ["started_at", "completed_at"],
)
def test_rejects_naive_timestamps(valid_report_data, field):
    valid_report_data[field] = datetime.now()

    with pytest.raises(ValidationError):
        MetaMemoryMaintenanceReport(**valid_report_data)


def test_rejects_completion_before_start(valid_report_data):
    valid_report_data["completed_at"] = (
        valid_report_data["started_at"] - timedelta(seconds=1)
    )

    with pytest.raises(ValidationError):
        MetaMemoryMaintenanceReport(**valid_report_data)


def test_report_is_immutable(valid_report_data):
    report = MetaMemoryMaintenanceReport(**valid_report_data)

    with pytest.raises(ValidationError):
        report.assessed = 10


@pytest.mark.parametrize(
    "field",
    ["total_examined", "assessed", "skipped", "failed"],
)
def test_rejects_negative_counts(valid_report_data, field):
    valid_report_data[field] = -1

    with pytest.raises(ValidationError):
        MetaMemoryMaintenanceReport(**valid_report_data)
