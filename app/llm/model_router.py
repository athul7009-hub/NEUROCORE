
from enum import Enum

from app.core.config import settings


class TaskComplexity(str, Enum):
    SIMPLE = "simple"
    COMPLEX = "complex"
    STRUCTURED = "structured"


class ModelRouter:
    """Selects model settings based on task complexity."""

    def __init__(self, default_model: str | None = None):
        self.default_model = default_model or settings.ollama_model

    def classify(self, messages: list[dict[str, str]]) -> TaskComplexity:
        """Estimates task complexity using lightweight text rules."""

        user_message = next(
            (
                message["content"]
                for message in reversed(messages)
                if message.get("role") == "user"
                and isinstance(message.get("content"), str)
            ),
            "",
        ).strip().lower()

        complex_indicators = (
            "compare",
            "design",
            "architecture",
            "analyze",
            "analyse",
            "evaluate",
            "debug",
            "implement",
            "step by step",
            "pros and cons",
            "trade-offs",
            "tradeoffs",
            "comprehensive",
        )

        if (
            len(user_message) > 500
            or any(term in user_message for term in complex_indicators)
            or user_message.count("?") > 1
        ):
            return TaskComplexity.COMPLEX

        return TaskComplexity.SIMPLE

    def route(self, complexity: TaskComplexity) -> dict:
        """Returns the model and thinking configuration."""

        if not isinstance(complexity, TaskComplexity):
            raise ValueError("Invalid task complexity.")

        return {
            "model": self.default_model,
            "think": (
                True
                if complexity in (
                    TaskComplexity.COMPLEX,
                    TaskComplexity.STRUCTURED,
                )
                else False
            ),
        }
