
from uuid import UUID

from pydantic import ValidationError

from app.core.schemas import ToolRequest, ToolResult, ToolStatus
from app.tools.tool_registry import ToolRegistry
from app.tools.tool_approval_manager import ToolApprovalManager
from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_service import ToolApprovalService
from app.tools.tool_execution_ledger import (
    ExecutionState,
    ToolExecutionLedger,
)


class ToolExecutor:
    """Validates and executes registered tools with crash recovery."""

    def __init__(
        self,
        registry: ToolRegistry,
        approval_manager: ToolApprovalManager | None = None,
        approval_service: ToolApprovalService | None = None,
        execution_ledger: ToolExecutionLedger | None = None,
    ):
        self.registry = registry
        self.execution_ledger = execution_ledger

        if approval_service is not None:
            if (
                approval_manager is not None
                and approval_service.manager is not approval_manager
            ):
                raise ValueError(
                    "Approval service and manager must match."
                )

            if (
                execution_ledger is not None
                and approval_service.ledger is not None
                and approval_service.ledger is not execution_ledger
            ):
                raise ValueError(
                    "Approval service and execution ledger must match."
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
                execution_ledger,
            )

        if (
            execution_ledger is not None
            and self.approval_service.ledger is None
        ):
            self.approval_service.ledger = execution_ledger

    def approve(self, action_id: UUID) -> None:
        self.approval_service.approve(action_id)

    def reject(self, action_id: UUID) -> None:
        self.approval_service.reject(action_id)

    def _result(
        self,
        request: ToolRequest,
        status: ToolStatus,
        message: str,
    ) -> ToolResult:
        return ToolResult(
            action_id=request.action_id,
            status=status,
            success=False,
            message=message,
        )

    def execute(self, request: ToolRequest) -> ToolResult:
        action_id = request.action_id
        execution_started = False

        try:
            # 1. Find and validate the registered tool.
            tool = self.registry.get(request.tool_name)

            validated_input = tool.input_schema.model_validate(
                request.parameters
            )

            # 2. Never execute during dry-run.
            if request.dry_run:
                return self._result(
                    request,
                    ToolStatus.PROPOSED,
                    "Dry-run requested. Tool was not executed.",
                )

            manager = self.approval_manager
            ledger = self.execution_ledger

            # 3. Persistent execution-state checks.
            if ledger is not None:
                fingerprint = manager._generate_fingerprint(
                    request,
                    tool,
                )

                state = ledger.register(
                    action_id,
                    tool.name,
                    fingerprint,
                )

                if state == ExecutionState.INTERRUPTED:
                    return self._result(
                        request,
                        ToolStatus.FAILED,
                        "Execution was interrupted. Manual recovery is required; automatic retry is prohibited.",
                    )

                if state in (
                    ExecutionState.COMPLETED,
                    ExecutionState.FAILED,
                ):
                    return self._result(
                        request,
                        ToolStatus.FAILED,
                        "This action has already reached a terminal state.",
                    )

                if state == ExecutionState.REJECTED:
                    return self._result(
                        request,
                        ToolStatus.REJECTED,
                        "Tool action was rejected.",
                    )

                # 4. Approval-required execution.
                if tool.requires_approval:
                    if state == ExecutionState.PENDING_APPROVAL:

                        if manager.is_pending(action_id):
                            return self._result(
                                request,
                                ToolStatus.PROPOSED,
                                "Waiting for user approval.",
                            )

                        if (
                            manager.is_approved(action_id)
                            or manager.is_rejected(action_id)
                            or manager.is_consumed(action_id)
                        ):
                            raise ValueError(
                                "Approval state is inconsistent."
                            )

                        # Reconstruct pending approval after restart.
                        manager.register(request, tool)

                        return self._result(
                            request,
                            ToolStatus.PROPOSED,
                            "Tool requires explicit user approval.",
                        )

                    if state != ExecutionState.APPROVED:
                        raise ValueError(
                            "Invalid persistent approval state."
                        )

                    if not manager.consume_approval(request, tool):
                        raise ValueError(
                            "Tool approval validation failed."
                        )

                    if not ledger.transition(
                        action_id,
                        ExecutionState.APPROVED,
                        ExecutionState.EXECUTING,
                    ):
                        raise ValueError(
                            "Could not reserve action for execution."
                        )

                # 5. Tools that do not require approval.
                else:
                    if state != ExecutionState.PENDING_APPROVAL:
                        raise ValueError(
                            "Invalid state for a tool without approval."
                        )

                    if not ledger.transition(
                        action_id,
                        ExecutionState.PENDING_APPROVAL,
                        ExecutionState.EXECUTING,
                    ):
                        raise ValueError(
                            "Could not reserve action for execution."
                        )

                execution_started = True

            # 6. In-memory approval flow when no ledger is configured.
            elif tool.requires_approval:
                if manager.is_rejected(action_id):
                    return self._result(
                        request,
                        ToolStatus.REJECTED,
                        "Tool action was rejected.",
                    )

                if manager.is_consumed(action_id):
                    raise ValueError(
                        "Tool approval has already been consumed."
                    )

                if manager.is_pending(action_id):
                    return self._result(
                        request,
                        ToolStatus.PROPOSED,
                        "Waiting for user approval.",
                    )

                if manager.is_approved(action_id):
                    if not manager.consume_approval(request, tool):
                        raise ValueError(
                            "Tool approval validation failed."
                        )
                else:
                    manager.register(request, tool)

                    return self._result(
                        request,
                        ToolStatus.PROPOSED,
                        "Tool requires explicit user approval.",
                    )

                execution_started = True

            else:
                execution_started = True

            # 7. Execute the handler.
            try:
                result = tool.handler(validated_input)

            except Exception:
                if ledger is not None:
                    ledger.transition(
                        action_id,
                        ExecutionState.EXECUTING,
                        ExecutionState.FAILED,
                    )

                return self._result(
                    request,
                    ToolStatus.FAILED,
                    "Tool execution failed.",
                )

            # 8. Validate the handler's output.
            try:
                validated_output = tool.output_schema.model_validate(
                    result
                )

            except ValidationError:
                if ledger is not None:
                    ledger.transition(
                        action_id,
                        ExecutionState.EXECUTING,
                        ExecutionState.FAILED,
                    )

                return self._result(
                    request,
                    ToolStatus.FAILED,
                    "Tool output validation failed.",
                )

            # 9. Persist successful completion.
            if ledger is not None:
                if not ledger.transition(
                    action_id,
                    ExecutionState.EXECUTING,
                    ExecutionState.COMPLETED,
                ):
                    return self._result(
                        request,
                        ToolStatus.FAILED,
                        "Execution outcome could not be persisted. Manual recovery is required.",
                    )

            # 10. Return successful result.
            return ToolResult(
                action_id=action_id,
                status=ToolStatus.EXECUTED,
                success=True,
                message="Tool executed successfully.",
                data=validated_output.model_dump(mode="json"),
            )

        except ValidationError:
            if execution_started and self.execution_ledger is not None:
                self.execution_ledger.transition(
                    action_id,
                    ExecutionState.EXECUTING,
                    ExecutionState.FAILED,
                )

            return self._result(
                request,
                ToolStatus.FAILED,
                "Tool validation failed. Check the supplied input or tool output.",
            )

        except ValueError as error:
            return self._result(
                request,
                ToolStatus.FAILED,
                str(error),
            )

        except Exception:
            if execution_started and self.execution_ledger is not None:
                self.execution_ledger.transition(
                    action_id,
                    ExecutionState.EXECUTING,
                    ExecutionState.FAILED,
                )

            return self._result(
                request,
                ToolStatus.FAILED,
                "Tool execution failed.",
            )
