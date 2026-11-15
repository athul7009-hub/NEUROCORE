
from app.tools.tool_schemas import ToolDefinition


class ToolRegistry:
    """Registers and discovers available tools."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}


    def register(self, tool: ToolDefinition) -> None:
        if not tool.read_only and not tool.requires_approval:
            raise ValueError(
                "Write-capable tools must require explicit approval."
            )

        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")

        self._tools[tool.name] = tool


    def get(self, name: str) -> ToolDefinition:
        tool = self._tools.get(name)

        if tool is None:
            raise ValueError(f"Unknown tool: {name}")

        return tool

    def list_tools(self) -> list[str]:
        return sorted(self._tools)

    def list_definitions(self) -> list[ToolDefinition]:
        return list(self._tools.values())
