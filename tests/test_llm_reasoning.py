
import json
from uuid import uuid4

import pytest
from app.llm.schemas import ReasoningResponse
from app.llm.reasoning import (
    ReasoningResponseError,
    ReasoningService,
)
from app.llm.schemas import ReasoningRequest


class FakeOllamaClient:
    def __init__(self, response):
        self.response = response
        self.messages = None
        self.format = None

    def chat(self, messages, model=None, format=None):
        self.messages = messages
        self.format = format
        return self.response


def create_request():
    return ReasoningRequest(
        task_id=uuid4(),
        agent_name="PlanningAgent",
        objective="Create a Python project plan.",
        context="The project uses Python 3.11.",
    )


def create_response(request):
    return json.dumps({
        "request_id": str(request.request_id),
        "task_id": str(request.task_id),
        "reasoning_summary": "Divide the project into manageable stages.",
        "proposed_steps": [
            "Define requirements",
            "Design architecture",
            "Implement the application",
        ],
        "confidence": 0.9,
        "limitations": [],
    })


def test_generate_returns_validated_response():
    request = create_request()
    client = FakeOllamaClient(create_response(request))
    service = ReasoningService(client)

    response = service.generate(request)

    assert response.request_id == request.request_id
    assert response.task_id == request.task_id
    assert len(response.proposed_steps) == 3


def test_generate_uses_json_schema_output():
    request = create_request()
    client = FakeOllamaClient(create_response(request))
    service = ReasoningService(client)

    service.generate(request)

    assert client.format == ReasoningResponse.model_json_schema()


def test_generate_rejects_invalid_json():
    request = create_request()
    client = FakeOllamaClient("not valid JSON")
    service = ReasoningService(client)

    with pytest.raises(ReasoningResponseError):
        service.generate(request)


def test_generate_rejects_invalid_response_schema():
    request = create_request()

    invalid_response = json.dumps({
        "request_id": str(request.request_id),
        "task_id": str(request.task_id),
        "reasoning_summary": "A plan",
        "proposed_steps": [],
        "confidence": 0.9,
    })

    service = ReasoningService(FakeOllamaClient(invalid_response))

    with pytest.raises(ReasoningResponseError):
        service.generate(request)


def test_generate_rejects_mismatched_request_id():
    request = create_request()

    response = json.loads(create_response(request))
    response["request_id"] = str(uuid4())

    service = ReasoningService(
        FakeOllamaClient(json.dumps(response))
    )

    with pytest.raises(ReasoningResponseError):
        service.generate(request)


def test_generate_rejects_mismatched_task_id():
    request = create_request()

    response = json.loads(create_response(request))
    response["task_id"] = str(uuid4())

    service = ReasoningService(
        FakeOllamaClient(json.dumps(response))
    )

    with pytest.raises(ReasoningResponseError):
        service.generate(request)


def test_generate_does_not_expose_unrelated_request_fields():
    request = create_request()
    client = FakeOllamaClient(create_response(request))
    service = ReasoningService(client)

    service.generate(request)

    submitted = json.loads(client.messages[1]["content"])

    assert submitted["agent_name"] == "PlanningAgent"
    assert submitted["objective"] == request.objective
    assert submitted["context"] == request.context
    assert "execute_tool" not in submitted
