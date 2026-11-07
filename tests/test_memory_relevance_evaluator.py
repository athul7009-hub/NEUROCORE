from app.memory.context_schemas import MemoryContextItem
from app.memory.relevance_evaluator import MemoryRelevanceEvaluator
from datetime import datetime, timedelta, timezone

from uuid import uuid4

from app.memory.context_schemas import MemoryContextItem
from app.memory.relevance_evaluator import (
    MemoryRelevanceEvaluator,
    RelevanceLevel,
)
from app.memory.schemas import MemoryStatus


def make_memory(summary, status=MemoryStatus.COMPLETED, days_old=1):
    return MemoryContextItem(
        source_task_id=uuid4(),
        intent="PLAN_TASK",
        status=status,
        agent_name="PlanningAgent",
        summary=summary,
        completed_at=datetime.now(timezone.utc)
        - timedelta(days=days_old),
    )


def test_selects_directly_relevant_memory():
    evaluator = MemoryRelevanceEvaluator()
    memory = make_memory("Analyze Python project dependencies")

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [memory],
    )

    assert result.evaluations[0].relevance == RelevanceLevel.DIRECT
    assert result.evaluations[0].selected is True
    assert result.selected_memories == [memory]


def test_rejects_irrelevant_memory():
    evaluator = MemoryRelevanceEvaluator()
    memory = make_memory("Prepare restaurant menu database")

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [memory],
    )

    assert result.evaluations[0].relevance == RelevanceLevel.IRRELEVANT
    assert result.evaluations[0].selected is False
    assert result.selected_memories == []


def test_preserves_failed_memory_when_relevant():
    evaluator = MemoryRelevanceEvaluator()
    memory = make_memory(
        "Python project dependency analysis failed",
        MemoryStatus.FAILED,
    )

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [memory],
    )

    assert result.evaluations[0].selected is True
    assert "failed" in result.evaluations[0].reason.lower()


def test_evaluates_memories_independently():
    evaluator = MemoryRelevanceEvaluator()

    direct = make_memory("Analyze Python project dependencies")
    unrelated = make_memory("Prepare restaurant menu database")

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [direct, unrelated],
    )

    assert len(result.evaluations) == 2
    assert result.selected_memories == [direct]


def test_rejects_empty_objective():
    evaluator = MemoryRelevanceEvaluator()

    try:
        evaluator.evaluate("   ", [])
        assert False, "Expected ValueError"
    except ValueError:
        pass


def test_recent_memory_scores_higher_than_old_memory():
    evaluator = MemoryRelevanceEvaluator()
    recent = make_memory("Analyze Python project dependencies", days_old=1)
    old = make_memory("Analyze Python project dependencies", days_old=180)

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [recent, old],
    )

    assert result.evaluations[0].score > result.evaluations[1].score

def test_does_not_select_indirect_memory_even_when_recent():
    evaluator = MemoryRelevanceEvaluator()

    memory = make_memory(
        "Analyze restaurant inventory database",
        days_old=0,
    )

    result = evaluator.evaluate(
        "Analyze Python project dependencies",
        [memory],
    )

    evaluation = result.evaluations[0]

    assert evaluation.relevance == RelevanceLevel.INDIRECT
    assert evaluation.selected is False
    assert result.selected_memories == []

def test_rejects_future_memory_timestamp():
    evaluator = MemoryRelevanceEvaluator()

    now = datetime(2026, 11, 6, tzinfo=timezone.utc)

    memory = MemoryContextItem(
        source_task_id=uuid4(),
        intent="PLAN_TASK",
        status=MemoryStatus.COMPLETED,
        agent_name="PlanningAgent",
        summary="Analyze Python project dependencies",
        completed_at=now + timedelta(days=1),
    )

    try:
        evaluator.evaluate(
            "Analyze Python project dependencies",
            [memory],
            now=now,
        )
        assert False, "Expected ValueError"
    except ValueError as error:
        assert "future" in str(error).lower()
