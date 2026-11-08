import re
from datetime import datetime, timezone
from uuid import UUID

from app.memory.prospective_context_schemas import (
    ProspectiveMemoryContext,
    ProspectiveMemoryContextItem,
)
from app.memory.prospective_manager import ProspectiveMemoryManager
from app.memory.prospective_policy import ProspectiveMemoryPolicy


class ProspectiveMemoryContextBuilder:
    """Selects relevant pending intentions for an agent."""

    PRIORITY_WEIGHT = {
        "LOW": 1,
        "NORMAL": 2,
        "HIGH": 3,
        "CRITICAL": 4,
    }

    def __init__(
        self,
        manager: ProspectiveMemoryManager,
        limit: int = 5,
    ):
        if not isinstance(manager, ProspectiveMemoryManager):
            raise TypeError("A valid ProspectiveMemoryManager is required.")

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

    def _relevance_score(self, objective: str, memory) -> float:
        objective_tokens = self._tokenize(objective)

        memory_text = " ".join(
            filter(
                None,
                [
                    memory.title,
                    memory.description,
                    memory.action,
                    memory.trigger_condition,
                ],
            )
        )

        memory_tokens = self._tokenize(memory_text)

        if not objective_tokens or not memory_tokens:
            return 0.0

        overlap = objective_tokens.intersection(memory_tokens)

        return len(overlap) / len(objective_tokens)

    def build_context(
        self,
        *,
        task_id: UUID,
        objective: str,
        recipient_agent: str,
    ) -> ProspectiveMemoryContext:
        """Build a bounded context from relevant active intentions."""

        if not isinstance(task_id, UUID):
            raise TypeError("task_id must be a UUID.")

        if not isinstance(objective, str) or not objective.strip():
            raise ValueError("A valid objective is required.")

        if (
            not isinstance(recipient_agent, str)
            or recipient_agent not in ProspectiveMemoryPolicy.TRUSTED_AGENTS
        ):
            raise ValueError("A trusted recipient agent is required.")

        memories = self.manager.search(
            requesting_agent="CoordinatorAgent",
            limit=100,
        )

        now = datetime.now(timezone.utc)
        ranked = []

        for memory in memories:
            # Do not expose intentions that have already expired.
            if memory.expires_at is not None and memory.expires_at <= now:
                continue

            score = self._relevance_score(objective, memory)

            if score > 0:
                priority = self.PRIORITY_WEIGHT[memory.priority.name]

                ranked.append((score, priority, memory))

        ranked.sort(
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )

        selected = [
            ProspectiveMemoryContextItem(
                memory_id=memory.memory_id,
                title=memory.title,
                description=memory.description,
                action=memory.action,
                trigger_type=memory.trigger_type,
                trigger_condition=memory.trigger_condition,
                priority=memory.priority,
                status=memory.status,
                due_at=memory.due_at,
                expires_at=memory.expires_at,
            )
            for _, _, memory in ranked[:self.limit]
        ]

        return ProspectiveMemoryContext(
            task_id=task_id,
            recipient_agent=recipient_agent,
            memories=selected,
        )