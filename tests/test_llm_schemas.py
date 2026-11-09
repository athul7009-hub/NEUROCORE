
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.llm.schemas import ReasoningRequest, ReasoningResponse


def create_request():
    return ReasoningRequest(
        task_id=uuid4(),
        agent_name="PlanningAgent",
        objective="Create a Python project plan.",
    )


def create_response(request):
    return ReasoningResponse(
        request_id=request.request_id,
        task_id=request.task_id,
        reasoning_summary="Break the project into manageable steps.",
        proposed_steps=[
            "Define requirements",
            "Design architecture",
            "Implement the application",
        ],
        confidence=0.9,
    )


def test_reasoning_request_creation():
    request = create_request()

    assert request.agent_name == "PlanningAgent"
    assert request.objective == "Create a Python project plan."
    assert request.request_id is not None


def test_reasoning_request_rejects_empty_objective():
    with pytest.raises(ValidationError):
        ReasoningRequest(
            task_id=uuid4(),
            agent_name="PlanningAgent",
            objective="",
        )


def test_reasoning_request_rejects_extra_fields():
    with pytest.raises(ValidationError):
        ReasoningRequest(
            task_id=uuid4(),
            agent_name="PlanningAgent",
            objective="Create a project plan.",
            unauthorized=True,
        )


def test_reasoning_response_creation():
    request = create_request()
    response = create_response(request)

    assert response.task_id == request.task_id
    assert response.request_id == request.request_id
    assert len(response.proposed_steps) == 3
    assert response.confidence == 0.9
    assert response.limitations == []


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_reasoning_response_rejects_invalid_confidence(confidence):
    request = create_request()

    with pytest.raises(ValidationError):
        ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Test reasoning",
            proposed_steps=["Step 1"],
            confidence=confidence,
        )


def test_reasoning_response_rejects_empty_steps():
    request = create_request()

    with pytest.raises(ValidationError):
        ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Test reasoning",
            proposed_steps=[],
            confidence=0.8,
        )


def test_reasoning_response_rejects_extra_fields():
    request = create_request()

    with pytest.raises(ValidationError):
        ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Test reasoning",
            proposed_steps=["Step 1"],
            confidence=0.8,
            execute_tool=True,
        )
def test_reasoning_request_rejects_whitespace_objective():
    with pytest.raises(ValidationError):
        ReasoningRequest(
            task_id=uuid4(),
            agent_name="PlanningAgent",
            objective="   ",
        )


def test_reasoning_request_strips_whitespace():
    request = ReasoningRequest(
        task_id=uuid4(),
        agent_name=" PlanningAgent ",
        objective=" Create a project plan. ",
    )

    assert request.agent_name == "PlanningAgent"
    assert request.objective == "Create a project plan."


def test_reasoning_response_rejects_whitespace_summary():
    request = create_request()

    with pytest.raises(ValidationError):
        ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="   ",
            proposed_steps=["Step 1"],
            confidence=0.8,
        )


def test_reasoning_response_rejects_whitespace_steps():
    request = create_request()

    with pytest.raises(ValidationError):
        ReasoningResponse(
            request_id=request.request_id,
            task_id=request.task_id,
            reasoning_summary="Valid summary",
            proposed_steps=["Step 1", "   "],
            confidence=0.8,
        )


def test_reasoning_response_strips_whitespace():
    request = create_request()

    response = ReasoningResponse(
        request_id=request.request_id,
        task_id=request.task_id,
        reasoning_summary=" Valid summary ",
        proposed_steps=[" Step 1 ", " Step 2 "],
        confidence=0.8,
    )

    assert response.reasoning_summary == "Valid summary"
    assert response.proposed_steps == ["Step 1", "Step 2"]