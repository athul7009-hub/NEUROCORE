
import pytest

from app.llm.model_router import ModelRouter, TaskComplexity


def test_simple_task_disables_thinking():
    router = ModelRouter(default_model="qwen3:8b")

    result = router.route(TaskComplexity.SIMPLE)

    assert result == {
        "model": "qwen3:8b",
        "think": False,
    }


def test_complex_task_enables_thinking():
    router = ModelRouter(default_model="qwen3:8b")

    result = router.route(TaskComplexity.COMPLEX)

    assert result["think"] is True


def test_structured_task_enables_thinking():
    router = ModelRouter(default_model="qwen3:8b")

    result = router.route(TaskComplexity.STRUCTURED)

    assert result["think"] is True


def test_router_uses_configured_model():
    router = ModelRouter(default_model="llama3:latest")

    result = router.route(TaskComplexity.SIMPLE)

    assert result["model"] == "llama3:latest"


def test_router_rejects_invalid_complexity():
    router = ModelRouter(default_model="qwen3:8b")

    with pytest.raises(ValueError):
        router.route("unknown")

def test_classifies_simple_message():
    router = ModelRouter()

    result = router.classify([
        {"role": "user", "content": "What is Python?"}
    ])

    assert result == TaskComplexity.SIMPLE


def test_classifies_complex_message():
    router = ModelRouter()

    result = router.classify([
        {
            "role": "user",
            "content": "Compare Python and Java.",
        }
    ])

    assert result == TaskComplexity.COMPLEX


def test_classifies_long_message():
    router = ModelRouter()

    result = router.classify([
        {"role": "user", "content": "Explain this. " * 50}
    ])

    assert result == TaskComplexity.COMPLEX
