import re
from uuid import UUID

from app.memory.semantic_manager import SemanticMemoryManager
from app.memory.semantic_context_schemas import (
    SemanticMemoryContext,
    SemanticMemoryContextItem,
)


class SemanticMemoryContextBuilder:
    """Builds relevant, bounded semantic context for agents."""

    MAX_CONTEXT_ITEMS = 10
    CANDIDATE_LIMIT = 100

    def __init__(self, memory_manager: SemanticMemoryManager):
        self.memory_manager = memory_manager

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9]+", text.lower())
            if len(token) > 1
        }

    def build_context(
        self,
        *,
        task_id: UUID,
        recipient_agent: str,
        objective: str,
    ) -> SemanticMemoryContext:
        if (
            not isinstance(recipient_agent, str)
            or recipient_agent not in self.memory_manager.policy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized semantic context recipient."
            )

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("A valid semantic context objective is required.")

        query_tokens = self._tokenize(objective)

        records = self.memory_manager.search(
            requesting_agent="CoordinatorAgent",
            limit=self.CANDIDATE_LIMIT,
        )

        ranked = []

        for record in records:
            memory_text = (
                f"{record.subject} "
                f"{record.predicate} "
                f"{record.object}"
            )

            memory_tokens = self._tokenize(memory_text)
            overlap = query_tokens.intersection(memory_tokens)

            if not overlap:
                continue

            relevance = len(overlap) / len(query_tokens)

            score = (
                relevance * 0.8
                + record.confidence * 0.2
            )

            ranked.append((score, record))

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1].confidence,
                item[1].updated_at,
            ),
            reverse=True,
        )

        selected = [
            SemanticMemoryContextItem(
                memory_id=record.memory_id,
                subject=record.subject,
                predicate=record.predicate,
                object=record.object,
                confidence=record.confidence,
                source=record.source,
                validated_at=record.validated_at,
                validated_by=record.validated_by,
            )
            for _, record in ranked[:self.MAX_CONTEXT_ITEMS]
        ]

        return SemanticMemoryContext(
            task_id=task_id,
            recipient_agent=recipient_agent,
            memories=selected,
        )