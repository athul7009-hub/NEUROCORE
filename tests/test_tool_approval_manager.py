
import pytest

from app.core.schemas import ToolRequest
from app.tools.tool_approval_manager import ToolApprovalManager
from app.tools.tool_schemas import ToolDefinition
from pydantic import BaseModel
from uuid import UUID

from concurrent.futures import ThreadPoolExecutor
class SampleInput(BaseModel):
    value: str


class SampleOutput(BaseModel):
    result: str


def create_tool() -> ToolDefinition:
    return ToolDefinition(
        name="sample",
        description="Sample tool",
        handler=lambda request: {"result": request.value},
        input_schema=SampleInput,
        output_schema=SampleOutput,
        requires_approval=True,
        read_only=False,
    )


def create_request() -> ToolRequest:
    return ToolRequest(
        tool_name="sample",
        parameters={"value": "hello"},
        dry_run=False,
    )


def test_register_pending_approval():
    manager = ToolApprovalManager()
    request = create_request()

    manager.register(request, create_tool())

    assert request.action_id in manager._pending


def test_register_rejects_tool_name_mismatch():
    manager = ToolApprovalManager()
    request = create_request()

    tool = create_tool()

    with pytest.raises(ValueError):
        manager.register(
            request.model_copy(update={"tool_name": "other"}),
            tool,
        )


def test_register_rejects_tool_without_approval_requirement():
    manager = ToolApprovalManager()
    request = create_request()

    tool = create_tool()
    tool = ToolDefinition(
        **{
            **tool.model_dump(),
            "requires_approval": False,
        }
    )

    with pytest.raises(ValueError):
        manager.register(request, tool)


def test_register_rejects_duplicate_action():
    manager = ToolApprovalManager()
    request = create_request()
    tool = create_tool()

    manager.register(request, tool)

    with pytest.raises(ValueError):
        manager.register(request, tool)


def test_approved_request_can_be_consumed_once():
    manager = ToolApprovalManager()
    request = create_request()
    tool = create_tool()

    manager.register(request, tool)
    manager.approve(request.action_id)

    assert manager.consume_approval(request, tool) is True
    assert manager.consume_approval(request, tool) is False


def test_modified_request_cannot_use_approval():
    manager = ToolApprovalManager()
    request = create_request()
    tool = create_tool()

    manager.register(request, tool)
    manager.approve(request.action_id)

    modified_request = request.model_copy(
        update={"parameters": {"value": "modified"}}
    )

    assert manager.consume_approval(modified_request, tool) is False


def test_rejected_request_cannot_be_approved():
    manager = ToolApprovalManager()
    request = create_request()

    manager.register(request, create_tool())
    manager.reject(request.action_id)
    assert manager.is_rejected(request.action_id)
    assert not manager.is_pending(request.action_id)
    assert not manager.is_approved(request.action_id)

    with pytest.raises(ValueError):
        manager.approve(request.action_id)



def test_approval_can_only_be_consumed_once_concurrently():
    manager = ToolApprovalManager()
    request = create_request()
    tool = create_tool()

    manager.register(request, tool)
    manager.approve(request.action_id)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(
            executor.map(
                lambda _: manager.consume_approval(request, tool),
                range(20),
            )
        )

    assert results.count(True) == 1
    assert results.count(False) == 19
    assert manager.is_consumed(request.action_id)
def test_modified_tool_schema_cannot_use_approval():
    class ModifiedOutput(BaseModel):
        result: str
        extra: str

    manager = ToolApprovalManager()
    request = create_request()
    tool = create_tool()

    manager.register(request, tool)
    manager.approve(request.action_id)

    modified_tool = ToolDefinition(
        name=tool.name,
        description=tool.description,
        version=tool.version,
        handler=tool.handler,
        input_schema=tool.input_schema,
        output_schema=ModifiedOutput,
        requires_approval=True,
        read_only=False,
    )

    assert manager.consume_approval(
        request,
        modified_tool,
    ) is False

    assert manager.is_consumed(request.action_id)
def test_registration_metadata_is_removed_after_approval():
    manager = ToolApprovalManager()
    request = create_request()

    manager.register(request, create_tool())

    assert manager.get_pending_tool_name(request.action_id) == "sample"

    manager.approve(request.action_id)

    with pytest.raises(ValueError):
        manager.get_pending_tool_name(request.action_id)


def test_registration_metadata_is_removed_after_rejection():
    manager = ToolApprovalManager()
    request = create_request()

    manager.register(request, create_tool())
    manager.reject(request.action_id)

    with pytest.raises(ValueError):
        manager.get_pending_tool_name(request.action_id)