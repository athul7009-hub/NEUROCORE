
from pydantic import ValidationError

from app.core.schemas import ToolRequest, ToolResult, ToolStatus
from app.tools.tool_registry import ToolRegistry
from uuid import UUID
from app.tools.tool_approval_manager import ToolApprovalManager
from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_service import ToolApprovalService
class ToolExecutor:
    """Validates and executes registered tools."""

    def __init__(
        self,
        registry: ToolRegistry,
        approval_manager: ToolApprovalManager | None = None,
        approval_service: ToolApprovalService | None = None,
    ):
        self.registry = registry

        if approval_service is not None:
            if (
                approval_manager is not None
                and approval_service.manager is not approval_manager
            ):
                raise ValueError(
                    "Approval service and manager must match."
                )

            self.approval_service = approval_service
            self.approval_manager = approval_service.manager
        else:
            self.approval_manager = (
                approval_manager or ToolApprovalManager()
            )
            self.approval_service = ToolApprovalService(
                self.approval_manager,
                ToolApprovalAudit(),
            )

    def approve(self, action_id: UUID) -> None:
        self.approval_service.approve(action_id)

    def reject(self, action_id: UUID) -> None:
        self.approval_service.reject(action_id)
    def execute(self, request: ToolRequest) -> ToolResult:
        try:
            tool = self.registry.get(request.tool_name)

            validated_input = tool.input_schema.model_validate(
                request.parameters
            )

            action_id = request.action_id

            if request.dry_run:
                return ToolResult(
                    action_id=action_id,
                    status=ToolStatus.PROPOSED,
                    success=False,
                    message="Dry-run requested. Tool was not executed.",
                )

            if tool.requires_approval:
                manager = self.approval_manager

                if manager.is_rejected(action_id):
                    return ToolResult(
                        action_id=action_id,
                        status=ToolStatus.REJECTED,
                        success=False,
                        message="Tool action was rejected.",
                    )

                if manager.is_consumed(action_id):
                    raise ValueError("Tool approval has already been consumed.")

                if manager.is_pending(action_id):
                    return ToolResult(
                        action_id=action_id,
                        status=ToolStatus.PROPOSED,
                        success=False,
                        message="Waiting for user approval.",
                    )

                if manager.is_approved(action_id):
                    if not manager.consume_approval(request, tool):
                        raise ValueError("Tool approval validation failed.")
                else:
                    manager.register(request, tool)

                    return ToolResult(
                        action_id=action_id,
                        status=ToolStatus.PROPOSED,
                        success=False,
                        message="Tool requires explicit user approval.",
                    )

            try:
                result = tool.handler(validated_input)
            except Exception:
                return ToolResult(
                    action_id=action_id,
                    status=ToolStatus.FAILED,
                    success=False,
                    message="Tool execution failed.",
                )

            validated_output = tool.output_schema.model_validate(result)

            return ToolResult(
                action_id=action_id,
                status=ToolStatus.EXECUTED,
                success=True,
                message="Tool executed successfully.",
                data=validated_output.model_dump(mode="json"),
            )

        except ValidationError as error:
            return ToolResult(
                action_id=request.action_id,
                status=ToolStatus.FAILED,
                success=False,
                message="Tool validation failed. Check the supplied input or tool output.",
            )

        except ValueError as error:
            return ToolResult(
                action_id=request.action_id,
                status=ToolStatus.FAILED,
                success=False,
                message=str(error),
            )

        except Exception:
            return ToolResult(
                action_id=request.action_id,
                status=ToolStatus.FAILED,
                success=False,
                message="Tool execution failed.",
            )
