
import re
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.memory.context_schemas import MemoryContextItem
from app.memory.schemas import MemoryStatus


class RelevanceLevel(str, Enum):
    DIRECT = "direct"
    RELATED = "related"
    INDIRECT = "indirect"
    IRRELEVANT = "irrelevant"


class MemoryEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_task_id: str
    relevance: RelevanceLevel
    score: float = Field(ge=0, le=1)
    selected: bool
    reason: str = Field(min_length=1)


class MemoryEvaluationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evaluations: list[MemoryEvaluation] = Field(default_factory=list)
    selected_memories: list[MemoryContextItem] = Field(
        default_factory=list
    )


class MemoryRelevanceEvaluator:
    """Evaluates historical memories against a current objective."""

    SELECTION_THRESHOLD = 0.35

    STOP_WORDS = {
        "a", "an", "the", "and", "or", "to", "of", "in",
        "on", "for", "with", "my", "me", "is", "are",
        "was", "were", "this", "that", "it", "by",
    }

    def evaluate(
        self,
        objective: str,
        memories: list[MemoryContextItem],
        now: datetime | None = None,
    ) -> MemoryEvaluationResult:
        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("A valid objective is required.")

        if not isinstance(memories, list):
            raise TypeError("Memories must be provided as a list.")

        now = now or datetime.now(timezone.utc)

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("Evaluation time must be timezone-aware.")

        evaluations = []
        selected_memories = []

        objective_terms = self._terms(objective)

        for memory in memories:
            similarity = self._similarity(
                objective_terms,
                self._terms(memory.summary),
            )

            recency = self._recency(memory.completed_at, now)

            outcome = (
                1.0
                if memory.status == MemoryStatus.COMPLETED
                else 0.8
            )

            score = (
                similarity * 0.60
                + recency * 0.25
                + outcome * 0.15
            )

            relevance = self._classify(similarity)

            selected = (
                relevance in {
                    RelevanceLevel.DIRECT,
                    RelevanceLevel.RELATED,
                }
                and score >= self.SELECTION_THRESHOLD
            )

            reason = self._reason(
                relevance,
                similarity,
                memory.status,
            )

            evaluations.append(
                MemoryEvaluation(
                    source_task_id=str(memory.source_task_id),
                    relevance=relevance,
                    score=round(score, 3),
                    selected=selected,
                    reason=reason,
                )
            )

            if selected:
                selected_memories.append(memory)

        return MemoryEvaluationResult(
            evaluations=evaluations,
            selected_memories=selected_memories,
        )

    @classmethod
    def _terms(cls, text: str) -> set[str]:
        return {
            word
            for word in re.findall(r"\b[a-z0-9_]+\b", text.lower())
            if word not in cls.STOP_WORDS and len(word) > 2
        }

    @staticmethod
    def _similarity(
        objective_terms: set[str],
        memory_terms: set[str],
    ) -> float:
        if not objective_terms or not memory_terms:
            return 0.0

        intersection = objective_terms & memory_terms
        union = objective_terms | memory_terms

        return len(intersection) / len(union)

    @staticmethod
    def _recency(
        completed_at: datetime,
        now: datetime,
    ) -> float:
        if completed_at.tzinfo is None or completed_at.utcoffset() is None:
            raise ValueError("Memory timestamp must be timezone-aware.")

        age_seconds = (now - completed_at).total_seconds()

        if age_seconds < 0:
            raise ValueError("Memory timestamp cannot be in the future.")

        age_days = age_seconds / 86400

        return 0.5 ** (age_days / 30)

    @staticmethod
    def _classify(similarity: float) -> RelevanceLevel:
        if similarity >= 0.50:
            return RelevanceLevel.DIRECT

        if similarity >= 0.25:
            return RelevanceLevel.RELATED

        if similarity >= 0.10:
            return RelevanceLevel.INDIRECT

        return RelevanceLevel.IRRELEVANT

    @staticmethod
    def _reason(
        relevance: RelevanceLevel,
        similarity: float,
        status: MemoryStatus,
    ) -> str:
        outcome = (
            "Previous task completed successfully."
            if status == MemoryStatus.COMPLETED
            else "Previous task failed; its experience may help avoid similar failures."
        )

        return (
            f"{relevance.value.title()} relevance "
            f"(similarity: {similarity:.2f}). {outcome}"
        )
