
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from app.memory.meta_assessment_schemas import MetaMemoryAssessment
from app.memory.meta_schemas import MetaMemoryStalenessStatus


def create_assessment(**overrides):
    data = {
        "quality_score": 0.8,
        "assessment_confidence": 0.9,
        "staleness_status": MetaMemoryStalenessStatus.CURRENT,
        "rationale": "Frequently retrieved and recently accessed.",
    }
    data.update(overrides)
    return MetaMemoryAssessment(**data)


def test_create_valid_assessment():
    assessment = create_assessment()

    assert assessment.quality_score == 0.8
    assert assessment.assessment_confidence == 0.9
    assert assessment.staleness_status == MetaMemoryStalenessStatus.CURRENT


def test_quality_score_can_be_none():
    assessment = create_assessment(quality_score=None)

    assert assessment.quality_score is None


@pytest.mark.parametrize("score", [-0.1, 1.1])
def test_rejects_invalid_quality_score(score):
    with pytest.raises(ValidationError):
        create_assessment(quality_score=score)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_rejects_invalid_assessment_confidence(confidence):
    with pytest.raises(ValidationError):
        create_assessment(assessment_confidence=confidence)


def test_rejects_naive_assessment_timestamp():
    with pytest.raises(ValidationError):
        create_assessment(
            assessed_at=datetime(2026, 1, 1)
        )


def test_accepts_timezone_aware_timestamp():
    timestamp = datetime.now(timezone.utc)

    assessment = create_assessment(assessed_at=timestamp)

    assert assessment.assessed_at == timestamp


def test_assessed_at_defaults_to_current_time():
    before = datetime.now(timezone.utc)
    assessment = create_assessment()
    after = datetime.now(timezone.utc)

    assert before <= assessment.assessed_at <= after


@pytest.mark.parametrize("rationale", ["", " ", "\n"])
def test_rejects_blank_rationale(rationale):
    with pytest.raises(ValidationError):
        create_assessment(rationale=rationale)


def test_strips_rationale_whitespace():
    assessment = create_assessment(rationale="  Useful memory.  ")

    assert assessment.rationale == "Useful memory."


def test_rejects_rationale_longer_than_500_characters():
    with pytest.raises(ValidationError):
        create_assessment(rationale="x" * 501)


def test_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        create_assessment(unexpected_field="value")


def test_assessment_is_immutable():
    assessment = create_assessment()

    with pytest.raises(ValidationError):
        assessment.quality_score = 0.5


def test_assessment_is_independent_of_meta_memory_record():
    assessment = create_assessment()

    assert not hasattr(assessment, "memory_id")
    assert not hasattr(assessment, "meta_id")
