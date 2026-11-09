
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from app.memory.meta_assessment_schemas import MetaMemoryAssessment
from app.memory.meta_manager import MetaMemoryManager
from app.memory.meta_policy import MetaMemoryPolicy
from app.memory.meta_schemas import (
    MetaMemoryRecord,
    MetaMemoryStalenessStatus,
    MetaMemoryType,
)
from app.memory.repositories.meta_memory import MetaMemoryRepository


@pytest.fixture
def manager(tmp_path):
    from app.memory.database import SQLiteDatabase

    database = SQLiteDatabase(tmp_path / "meta_manager.db")
    repository = MetaMemoryRepository(database)
    instance = MetaMemoryManager(repository)
    instance.initialize()
    return instance


@pytest.fixture
def record():
    return MetaMemoryRecord(
        memory_type=MetaMemoryType.EPISODIC,
        memory_id="memory-001",
    )


def test_remember_stores_metadata(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    stored = manager.get_for_memory(
        MetaMemoryType.EPISODIC,
        "memory-001",
        requesting_agent="CoordinatorAgent",
    )

    assert stored == record


def test_only_coordinator_can_store_metadata(manager, record):
    with pytest.raises(PermissionError):
        manager.remember(record, requesting_agent="PlanningAgent")


def test_rejects_invalid_record(manager):
    with pytest.raises(TypeError):
        manager.remember(
            {"memory_id": "memory-001"},
            requesting_agent="CoordinatorAgent",
        )


def test_retrieves_metadata_by_id(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    result = manager.get(
        record.meta_id,
        requesting_agent="PlanningAgent",
    )

    assert result == record


def test_rejects_untrusted_retrieval(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(PermissionError):
        manager.get(
            record.meta_id,
            requesting_agent="UnknownAgent",
        )


def test_returns_none_for_missing_metadata(manager):
    assert manager.get(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is None


def test_get_for_memory_retrieves_correct_metadata(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    result = manager.get_for_memory(
        MetaMemoryType.EPISODIC,
        "memory-001",
        requesting_agent="PlanningAgent",
    )

    assert result == record


def test_search_returns_metadata(manager):
    for index in range(3):
        manager.remember(
            MetaMemoryRecord(
                memory_type=MetaMemoryType.EPISODIC,
                memory_id=f"memory-{index}",
            ),
            requesting_agent="CoordinatorAgent",
        )

    results = manager.search(requesting_agent="PlanningAgent")

    assert len(results) == 3


def test_assessment_update_changes_only_assessment_fields(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    result = manager.update_assessment(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        quality_score=0.9,
        assessment_confidence=0.85,
        staleness_status=MetaMemoryStalenessStatus.CURRENT,
    )

    assert result is True

    updated = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated.quality_score == 0.9
    assert updated.assessment_confidence == 0.85
    assert updated.staleness_status == MetaMemoryStalenessStatus.CURRENT
    assert updated.memory_type == record.memory_type
    assert updated.memory_id == record.memory_id
    assert updated.usage_count == record.usage_count
    assert updated.last_assessed_at is not None


@pytest.mark.parametrize(
    "quality_score, assessment_confidence",
    [
        (-0.1, 0.8),
        (1.1, 0.8),
        (0.8, -0.1),
        (0.8, 1.1),
    ],
)
def test_rejects_invalid_assessment_scores(
    manager,
    record,
    quality_score,
    assessment_confidence,
):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(ValueError):
        manager.update_assessment(
            record.meta_id,
            requesting_agent="CoordinatorAgent",
            quality_score=quality_score,
            assessment_confidence=assessment_confidence,
            staleness_status=MetaMemoryStalenessStatus.CURRENT,
        )


def test_only_coordinator_can_update_assessment(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(PermissionError):
        manager.update_assessment(
            record.meta_id,
            requesting_agent="PlanningAgent",
            quality_score=0.9,
            assessment_confidence=0.8,
            staleness_status=MetaMemoryStalenessStatus.CURRENT,
        )


def test_update_assessment_returns_false_for_missing_record(manager):
    assert manager.update_assessment(
        uuid4(),
        requesting_agent="CoordinatorAgent",
        quality_score=0.9,
        assessment_confidence=0.8,
        staleness_status=MetaMemoryStalenessStatus.CURRENT,
    ) is False


def test_trusted_agent_can_record_usage(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    result = manager.record_usage(
        MetaMemoryType.EPISODIC,
        record.memory_id,
        requesting_agent="PlanningAgent",
    )

    assert result is True

    updated = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated.usage_count == 1
    assert updated.last_retrieved_at is not None


def test_untrusted_agent_cannot_record_usage(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(PermissionError):
        manager.record_usage(
            MetaMemoryType.EPISODIC,
            record.memory_id,
            requesting_agent="UnknownAgent",
        )


def test_usage_tracking_does_not_create_metadata(manager):
    result = manager.record_usage(
        MetaMemoryType.EPISODIC,
        "missing-memory",
        requesting_agent="PlanningAgent",
    )

    assert result is False


def test_usage_tracking_increments_existing_count(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    for _ in range(3):
        manager.record_usage(
            MetaMemoryType.EPISODIC,
            record.memory_id,
            requesting_agent="PlanningAgent",
        )

    updated = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated.usage_count == 3


def test_usage_tracking_accepts_explicit_timestamp(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")
    retrieved_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    manager.record_usage(
        MetaMemoryType.EPISODIC,
        record.memory_id,
        requesting_agent="PlanningAgent",
        retrieved_at=retrieved_at,
    )

    updated = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated.last_retrieved_at == retrieved_at


def test_assessment_update_rejects_invalid_staleness_status(
    manager,
    record,
):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(TypeError):
        manager.update_assessment(
            record.meta_id,
            requesting_agent="CoordinatorAgent",
            quality_score=0.9,
            assessment_confidence=0.8,
            staleness_status="current",
        )
def test_assess_returns_assessment_without_persisting_changes(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    assessment = manager.assess(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert isinstance(assessment, MetaMemoryAssessment)
    assert assessment.quality_score is None
    assert assessment.assessment_confidence == 0.0

    stored = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored.quality_score is None
    assert stored.assessment_confidence is None
    assert stored.last_assessed_at is None


def test_only_coordinator_can_assess(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(PermissionError):
        manager.assess(
            record.meta_id,
            requesting_agent="PlanningAgent",
        )


def test_assess_rejects_invalid_metadata_id(manager):
    with pytest.raises(TypeError):
        manager.assess(
            "invalid-id",
            requesting_agent="CoordinatorAgent",
        )


def test_assess_returns_none_for_missing_record(manager):
    assert manager.assess(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    ) is None


def test_assess_uses_supplied_timestamp(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")
    assessed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    assessment = manager.assess(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        now=assessed_at,
    )

    assert assessment.assessed_at == assessed_at


def test_assess_uses_injected_assessment_engine(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    expected = MetaMemoryAssessment(
        quality_score=0.8,
        assessment_confidence=0.6,
        staleness_status=MetaMemoryStalenessStatus.CURRENT,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rationale="Test assessment",
    )

    class StubAssessmentEngine:
        def __init__(self):
            self.received_record = None
            self.received_now = None

        def assess(self, received_record, *, now=None):
            self.received_record = received_record
            self.received_now = now
            return expected

    engine = StubAssessmentEngine()
    custom_manager = MetaMemoryManager(
        manager.repository,
        assessment_engine=engine,
    )

    result = custom_manager.assess(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        now=expected.assessed_at,
    )

    assert result is expected
    assert engine.received_record == record
    assert engine.received_now == expected.assessed_at

def test_persists_inconclusive_assessment(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    manager.record_usage(
        MetaMemoryType.EPISODIC,
        record.memory_id,
        requesting_agent="PlanningAgent",
    )

    result = manager.update_assessment(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        quality_score=None,
        assessment_confidence=0.0,
        staleness_status=MetaMemoryStalenessStatus.CURRENT,
    )

    assert result is True

    updated = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert updated.quality_score is None
    assert updated.assessment_confidence == 0.0
    assert updated.last_assessed_at is not None
    assert updated.staleness_status == MetaMemoryStalenessStatus.CURRENT

    # Original memory identity and usage metadata remain unchanged.
    assert updated.meta_id == record.meta_id
    assert updated.memory_type == record.memory_type
    assert updated.memory_id == record.memory_id
    assert updated.usage_count == 1
    assert updated.last_retrieved_at is not None
def test_complete_assessment_workflow(manager, record):
    # 1. Store metadata.
    manager.remember(
        record,
        requesting_agent="CoordinatorAgent",
    )

    # 2. Record successful retrievals.
    for _ in range(5):
        manager.record_usage(
            MetaMemoryType.EPISODIC,
            record.memory_id,
            requesting_agent="PlanningAgent",
        )

    # 3. Generate an advisory assessment.
    assessed_at = datetime(2026, 11, 8, tzinfo=timezone.utc)

    assessment = manager.assess(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        now=assessed_at,
    )

    assert assessment is not None
    assert assessment.quality_score is not None
    assert assessment.assessment_confidence == 1.0
    assert assessment.staleness_status == MetaMemoryStalenessStatus.CURRENT

    # Assessment must not automatically persist.
    before_persistence = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert before_persistence.quality_score is None
    assert before_persistence.last_assessed_at is None

    # 4. Explicitly persist the assessment.
    result = manager.update_assessment(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        quality_score=assessment.quality_score,
        assessment_confidence=assessment.assessment_confidence,
        staleness_status=assessment.staleness_status,
    )

    assert result is True

    # 5. Verify persisted metadata.
    stored = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored.quality_score == assessment.quality_score
    assert stored.assessment_confidence == assessment.assessment_confidence
    assert stored.staleness_status == assessment.staleness_status
    assert stored.last_assessed_at is not None
    assert stored.usage_count == 5
    assert stored.memory_id == record.memory_id

def test_assess_and_persist_saves_generated_assessment(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    assessed_at = datetime.now(timezone.utc)

    assessment = manager.assess_and_persist(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
        now=assessed_at,
    )

    assert isinstance(assessment, MetaMemoryAssessment)
    assert assessment.quality_score is None
    assert assessment.assessment_confidence == 0.0

    stored = manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored.quality_score == assessment.quality_score
    assert stored.assessment_confidence == assessment.assessment_confidence
    assert stored.staleness_status == assessment.staleness_status
    assert stored.last_assessed_at == assessment.assessed_at


def test_assess_and_persist_returns_none_for_missing_record(manager):
    result = manager.assess_and_persist(
        uuid4(),
        requesting_agent="CoordinatorAgent",
    )

    assert result is None


def test_only_coordinator_can_assess_and_persist(manager, record):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    with pytest.raises(PermissionError):
        manager.assess_and_persist(
            record.meta_id,
            requesting_agent="PlanningAgent",
        )


def test_assess_and_persist_rejects_invalid_metadata_id(manager):
    with pytest.raises(TypeError):
        manager.assess_and_persist(
            "invalid-id",
            requesting_agent="CoordinatorAgent",
        )


def test_assess_and_persist_uses_generated_assessment_values(
    manager,
    record,
):
    manager.remember(record, requesting_agent="CoordinatorAgent")

    expected = MetaMemoryAssessment(
        quality_score=0.8,
        assessment_confidence=0.6,
        staleness_status=MetaMemoryStalenessStatus.CURRENT,
        assessed_at=datetime(2026, 11, 8, tzinfo=timezone.utc),
        rationale="Generated assessment",
    )

    class StubAssessmentEngine:
        def assess(self, received_record, *, now=None):
            assert received_record.meta_id == record.meta_id
            return expected

    custom_manager = MetaMemoryManager(
        manager.repository,
        assessment_engine=StubAssessmentEngine(),
    )

    result = custom_manager.assess_and_persist(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert result == expected

    stored = custom_manager.get(
        record.meta_id,
        requesting_agent="CoordinatorAgent",
    )

    assert stored.quality_score == 0.8
    assert stored.assessment_confidence == 0.6
    assert stored.staleness_status == MetaMemoryStalenessStatus.CURRENT
    assert stored.last_assessed_at == expected.assessed_at