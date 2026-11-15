
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from app.core.schemas import ToolRequest, ToolStatus
from app.tools.tool_executor import ToolExecutor
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_schemas import ToolDefinition


class SampleInput(BaseModel):
    value: str


class SampleOutput(BaseModel):
    result: str


def sample_handler(request: SampleInput) -> dict:
    return {"result": request.value}


def create_executor(
    requires_approval: bool = False,
) -> ToolExecutor:
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="sample",
            description="Sample test tool",
            handler=sample_handler,
            input_schema=SampleInput,
            output_schema=SampleOutput,
            requires_approval=requires_approval,
            read_only=True,
        )
    )

    return ToolExecutor(registry)


def test_execute_registered_tool():
    executor = create_executor()

    request = ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )

    result = executor.execute(request)

    assert result.success is True
    assert result.status == ToolStatus.EXECUTED
    assert result.data == {"result": "hello"}


def test_unknown_tool_returns_failed_result():
    executor = create_executor()

    result = executor.execute(
        ToolRequest(tool_name="unknown", dry_run=False)
    )

    assert result.success is False
    assert result.status == ToolStatus.FAILED


def test_invalid_input_returns_failed_result():
    executor = create_executor()

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"wrong": "value"},
            dry_run=False,
        )
    )

    assert result.success is False
    assert result.status == ToolStatus.FAILED
    assert "validation failed" in result.message.lower()


def test_approval_required_tool_is_not_executed():
    executor = create_executor(requires_approval=True)

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"value": "hello"},
            requires_approval=False,
            dry_run=False,
        )
    )

    assert result.success is False
    assert result.status == ToolStatus.PROPOSED, result.message

def test_dry_run_does_not_execute_tool():
    executor = create_executor()

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"value": "hello"},
            dry_run=True,
        )
    )

    assert result.success is False
    assert result.status == ToolStatus.PROPOSED



def test_invalid_output_returns_failed_result():
    registry = ToolRegistry()

    registry.register(
        ToolDefinition(
            name="sample",
            description="Sample test tool",
            handler=lambda request: {"wrong": "output"},
            input_schema=SampleInput,
            output_schema=SampleOutput,
            requires_approval=False,
            read_only=True,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"value": "hello"},
            dry_run=False,
        )
    )

    assert result.success is False
    assert result.status == ToolStatus.FAILED
    assert "validation failed" in result.message.lower()
def test_approved_tool_executes_only_once():
    executor = create_executor(requires_approval=True)

    request = ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )

    # First attempt registers the pending approval.
    first_result = executor.execute(request)

    assert first_result.status == ToolStatus.PROPOSED
    assert first_result.success is False

    # Repeated attempts must not execute the tool.
    second_result = executor.execute(request)

    assert second_result.status == ToolStatus.PROPOSED
    assert second_result.success is False

    # Explicit approval allows execution.
    executor.approve(request.action_id)

    approved_result = executor.execute(request)

    assert approved_result.status == ToolStatus.EXECUTED
    assert approved_result.success is True
    assert approved_result.data == {"result": "hello"}

    # Approval cannot be reused.
    repeated_result = executor.execute(request)

    assert repeated_result.status == ToolStatus.FAILED
    assert repeated_result.success is False
def test_rejected_tool_cannot_execute():
    executor = create_executor(requires_approval=True)

    request = ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )

    first_result = executor.execute(request)
    assert first_result.status == ToolStatus.PROPOSED

    executor.reject(request.action_id)

    rejected_result = executor.execute(request)

    assert rejected_result.status == ToolStatus.REJECTED
    assert rejected_result.success is False
    assert "rejected" in rejected_result.message.lower()
def test_modified_request_cannot_use_existing_approval():
    executor = create_executor(requires_approval=True)

    request = ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )

    first_result = executor.execute(request)
    assert first_result.status == ToolStatus.PROPOSED

    executor.approve(request.action_id)

    modified_request = request.model_copy(
        update={"parameters": {"value": "modified"}}
    )

    result = executor.execute(modified_request)

    assert result.status == ToolStatus.FAILED
    assert result.success is False
    assert "approval validation failed" in result.message.lower()


def test_validation_error_does_not_expose_submitted_values():
    executor = create_executor()
    secret = "SENSITIVE_TEST_VALUE"

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"unexpected": secret},
            dry_run=False,
        )
    )

    assert result.status == ToolStatus.FAILED
    assert "validation failed" in result.message.lower()
    assert secret not in result.message

def test_dry_run_never_calls_handler():
    calls = []

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sample",
            description="Sample test tool",
            handler=lambda request: calls.append(request),
            input_schema=SampleInput,
            output_schema=SampleOutput,
            requires_approval=False,
            read_only=True,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"value": "hello"},
            dry_run=True,
        )
    )

    assert result.status == ToolStatus.PROPOSED
    assert calls == []


def test_handler_exception_does_not_expose_internal_details():
    secret = r"C:\Private\secret.txt"

    def failing_handler(request):
        raise ValueError(f"Cannot access {secret}")

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sample",
            description="Failing test tool",
            handler=failing_handler,
            input_schema=SampleInput,
            output_schema=SampleOutput,
            requires_approval=False,
            read_only=True,
        )
    )

    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolRequest(
            tool_name="sample",
            parameters={"value": "hello"},
            dry_run=False,
        )
    )

    assert result.status == ToolStatus.FAILED
    assert result.message == "Tool execution failed."
    assert secret not in result.message


def test_approved_action_executes_only_once_concurrently():
    calls = []
    calls_lock = Lock()

    def counted_handler(request):
        with calls_lock:
            calls.append(request.value)

        return {"result": request.value}

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="sample",
            description="Concurrent execution test",
            handler=counted_handler,
            input_schema=SampleInput,
            output_schema=SampleOutput,
            requires_approval=True,
            read_only=False,
        )
    )

    executor = ToolExecutor(registry)

    request = ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )

    pending = executor.execute(request)
    assert pending.status == ToolStatus.PROPOSED

    executor.approve(request.action_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda _: executor.execute(request),
                range(20),
            )
        )

    executed = [
        result for result in results
        if result.status == ToolStatus.EXECUTED
    ]

    assert len(executed) == 1
    assert len(calls) == 1
    assert calls == ["hello"]
