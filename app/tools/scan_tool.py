
from app.tools.scan_pipeline import run_scan
from app.tools.tool_schemas import (
    ScanDirectoryInput,
    ScanDirectoryOutput,
    ToolDefinition,
)


def scan_directory_tool(
    request: ScanDirectoryInput,
) -> ScanDirectoryOutput:
    result = run_scan(request.directory)
    return ScanDirectoryOutput.model_validate(result)


SCAN_DIRECTORY_TOOL = ToolDefinition(
    name="scan_directory",
    description="Scan an approved directory and identify duplicate files.",
    handler=scan_directory_tool,
    input_schema=ScanDirectoryInput,
    output_schema=ScanDirectoryOutput,
    requires_approval=False,
    read_only=True,
)
