
from pydantic import BaseModel

from app.tools.tool_registry import ToolRegistry
from app.tools.tool_schemas import ToolDefinition


class SampleInput(BaseModel):
    value: str


class SampleOutput(BaseModel):
    result: str


def sample_handler(value: str) -> dict:
    return {"result": value}


def create_tool(name: str = "sample") -> ToolDefinition:
    return ToolDefinition(
        name=name,
        description="Sample test tool",
        handler=sample_handler,
        input_schema=SampleInput,
        output_schema=SampleOutput,
        requires_approval=False,
        read_only=True,
    )


def test_register_and_get_tool():
    registry = ToolRegistry()
    tool = create_tool()

    registry.register(tool)

    assert registry.get("sample") == tool


def test_register_rejects_duplicate_name():
    registry = ToolRegistry()
    registry.register(create_tool())

    try:
        registry.register(create_tool())
        assert False, "Expected duplicate registration to fail."
    except ValueError:
        pass


def test_get_rejects_unknown_tool():
    registry = ToolRegistry()

    try:
        registry.get("unknown")
        assert False, "Expected unknown tool lookup to fail."
    except ValueError:
        pass


def test_list_tools_returns_sorted_names():
    registry = ToolRegistry()
    registry.register(create_tool("zebra"))
    registry.register(create_tool("alpha"))

    assert registry.list_tools() == ["alpha", "zebra"]


def test_list_tools_returns_empty_list():
    assert ToolRegistry().list_tools() == []


def test_list_definitions_returns_registered_tools():
    registry = ToolRegistry()
    tool = create_tool()

    registry.register(tool)

    assert registry.list_definitions() == [tool]


def test_tool_definition_preserves_execution_policy():
    tool = create_tool()

    assert tool.requires_approval is False
    assert tool.read_only is True
    assert tool.input_schema is SampleInput
    assert tool.output_schema is SampleOutput

def test_register_rejects_write_tool_without_approval():
    registry = ToolRegistry()

    tool = ToolDefinition(
        name="unsafe_write",
        description="Unsafe write tool",
        handler=sample_handler,
        input_schema=SampleInput,
        output_schema=SampleOutput,
        requires_approval=False,
        read_only=False,
    )

    try:
        registry.register(tool)
        assert False, "Expected unsafe tool registration to fail."
    except ValueError as error:
        assert "explicit approval" in str(error).lower()
import pytest


def test_registered_tool_definition_is_immutable():
    registry = ToolRegistry()
    tool = create_tool()

    registry.register(tool)

    registered_tool = registry.get("sample")

    with pytest.raises(Exception):
        registered_tool.requires_approval = True

    assert registry.get("sample").requires_approval is False