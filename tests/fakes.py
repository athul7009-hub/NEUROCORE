
from app.agents.planning_agent import PlanningAgent
import json

from app.llm.schemas import ReasoningResponse


class MockReasoningService:
    def generate(self, request):
        try:
            context = json.loads(request.context or "{}")
        except json.JSONDecodeError:
            context = {}

        episodic_memories = context.get("episodic", [])

        has_completed_memory = any(
            memory.get("status") == "completed"
            for memory in episodic_memories
        )

        has_failed_memory = any(
            memory.get("status") == "failed"
            for memory in episodic_memories
        )

        steps = [
            "Inspect the project structure.",
            "Identify the main components.",
            "Analyze dependencies.",
            "Determine required improvements.",
            "Prepare the implementation plan.",
        ]

        if has_completed_memory:
            steps[0] = (
                "Review previously completed tasks and their findings."
            )
        elif has_failed_memory:
            steps[0] = (
                "Review previous failures and include preventive checks."
            )

        return ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Mock planning response.",
            proposed_steps=steps,
            confidence=0.9,
        )


def create_planning_agent():
    return PlanningAgent(
        reasoning_service=MockReasoningService()
    )
