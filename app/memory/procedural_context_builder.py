
import re
from uuid import UUID

from app.memory.procedural_context_schemas import (
    ProceduralMemoryContext,
    ProceduralMemoryContextItem,
)
from app.memory.procedural_manager import ProceduralMemoryManager
from app.memory.procedural_policy import ProceduralMemoryPolicy

class ProceduralMemoryContextBuilder:
    """Selects relevant validated procedures for an agent."""

    def __init__(
        self,
        manager: ProceduralMemoryManager,
        limit: int = 5,
    ):
        if not isinstance(manager, ProceduralMemoryManager):
            raise TypeError("A valid ProceduralMemoryManager is required.")

        if type(limit) is not int or not 1 <= limit <= 10:
            raise ValueError("Limit must be between 1 and 10.")

        self.manager = manager
        self.limit = limit

    @staticmethod
    def _tokenize(value: str) -> set[str]:
        return {
            token
            for token in re.findall(r"[a-zA-Z0-9]+", value.lower())
            if len(token) > 2
        }

    def _relevance_score(
        self,
        objective: str,
        procedure,
    ) -> float:
        objective_tokens = self._tokenize(objective)

        procedure_text = " ".join(
            [
                procedure.name,
                procedure.description,
                procedure.when_to_use,
            ]
        )

        procedure_tokens = self._tokenize(procedure_text)

        if not objective_tokens or not procedure_tokens:
            return 0.0

        overlap = objective_tokens.intersection(procedure_tokens)

        return len(overlap) / len(objective_tokens)

    def build_context(
        self,
        *,
        task_id: UUID,
        objective: str,
        recipient_agent: str,
    ) -> ProceduralMemoryContext:
        """Builds a bounded context from validated procedures."""

        if not isinstance(task_id, UUID):
            raise TypeError("task_id must be a UUID.")

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("A valid objective is required.")

        if (
            not isinstance(recipient_agent, str)
            or recipient_agent not in ProceduralMemoryPolicy.TRUSTED_AGENTS
        ):
            raise PermissionError(
                "Unauthorized procedural memory context recipient."
            )

        procedures = self.manager.search(
            requesting_agent="CoordinatorAgent",
            limit=100,
        )

        ranked = []

        for procedure in procedures:
            score = self._relevance_score(
                objective,
                procedure,
            )

            if score > 0:
                ranked.append(
                    (
                        score,
                        procedure.confidence,
                        procedure,
                    )
                )

        ranked.sort(
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )

        selected = [
            ProceduralMemoryContextItem(
                procedure_id=procedure.procedure_id,
                name=procedure.name,
                description=procedure.description,
                when_to_use=procedure.when_to_use,
                steps=procedure.steps,
                confidence=procedure.confidence,
                source=procedure.source,
            )
            for _, _, procedure in ranked[:self.limit]
        ]

        return ProceduralMemoryContext(
            task_id=task_id,
            recipient_agent=recipient_agent,
            memories=selected,
        )
