from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.memory.retention_policy import MemoryRetentionPolicy
from app.memory.schemas import (
    EpisodicMemoryRecord,
    MemoryLifecycleStatus,
    MemorySensitivity,
    MemoryStatus,
)


@pytest.fixture
def policy():
    return MemoryRetentionPolicy(
        min_age_days=90,
        inactivity_days=90,
        max_use_count=1,
    )


@pytest.fixture
def now():
    return datetime(2026, 11, 7, tzinfo=timezone.utc)


def create_record(**updates):
    now = datetime(2026, 11, 7, tzinfo=timezone.utc)
    old = now - timedelta(days=120)

    record = EpisodicMemoryRecord(
        task_id=uuid4(),
        intent="file_analysis",
        status=MemoryStatus.COMPLETED,
        agent_name="FileAnalysisAgent",
        summary="Analyzed project files.",
        created_at=old,
        completed_at=old,
        usage_tracked=True,
        use_count=0,
        last_used_at=old,
    )

    return record.model_copy(update=updates)


def test_old_inactive_low_usage_memory_is_eligible(policy, now):
    assessment = policy.assess(create_record(), now=now)

    assert assessment.eligible is True


def test_recent_memory_is_not_eligible(policy, now):
    recent = now - timedelta(days=30)

    record = create_record(
        created_at=recent,
        completed_at=recent,
        last_used_at=recent,
    )

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("minimum age" in reason for reason in assessment.reasons)


def test_recently_used_memory_is_not_eligible(policy, now):
    recent = now - timedelta(days=10)

    record = create_record(last_used_at=recent)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("inactivity threshold" in reason for reason in assessment.reasons)


def test_unknown_usage_history_is_protected(policy, now):
    record = create_record(usage_tracked=False)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any(
    "usage history is unknown" in reason.lower()
    for reason in assessment.reasons
)
def test_frequently_used_memory_is_protected(policy, now):
    record = create_record(use_count=2)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("usage exceeds" in reason for reason in assessment.reasons)


def test_failed_memory_is_protected(policy, now):
    record = create_record(status=MemoryStatus.FAILED)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("Failed memories" in reason for reason in assessment.reasons)


def test_explicitly_protected_memory_is_not_eligible(policy, now):
    record = create_record(is_protected=True)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("explicitly protected" in reason for reason in assessment.reasons)


@pytest.mark.parametrize(
    "sensitivity",
    [
        MemorySensitivity.CONFIDENTIAL,
        MemorySensitivity.RESTRICTED,
        MemorySensitivity.LEGACY_UNCLASSIFIED,
    ],
)
def test_protected_sensitivity_is_not_eligible(policy, now, sensitivity):
    record = create_record(sensitivity=sensitivity)

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False


def test_archived_memory_is_not_eligible(policy, now):
    record = create_record(
        lifecycle_status=MemoryLifecycleStatus.ARCHIVED,
    )

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("not active" in reason for reason in assessment.reasons)


def test_future_completion_timestamp_is_not_eligible(policy, now):
    record = create_record(
        completed_at=now + timedelta(days=1),
    )

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("future" in reason for reason in assessment.reasons)


def test_future_last_used_timestamp_is_not_eligible(policy, now):
    record = create_record(
        last_used_at=now + timedelta(days=1),
    )

    assessment = policy.assess(record, now=now)

    assert assessment.eligible is False
    assert any("future" in reason for reason in assessment.reasons)


def test_naive_assessment_time_is_rejected(policy):
    with pytest.raises(ValueError, match="timezone-aware"):
        policy.assess(
            create_record(),
            now=datetime(2026, 11, 7),
        )


def test_invalid_record_is_rejected(policy):
    with pytest.raises(TypeError):
        policy.assess({"summary": "Invalid"})