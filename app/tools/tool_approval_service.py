
from threading import Lock
from uuid import UUID

from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_manager import ToolApprovalManager
from app.tools.tool_execution_ledger import (
    ExecutionState,
    ToolExecutionLedger,
)


class ToolApprovalService:
    """Coordinates audited and persistent approval decisions."""

    def __init__(
        self,
        manager: ToolApprovalManager,
        audit: ToolApprovalAudit,
        ledger: ToolExecutionLedger | None = None,
    ):
        self.manager = manager
        self.audit = audit
        self.ledger = ledger
        self._lock = Lock()

    def approve(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "approved")

            if self.ledger is not None:
                if not self.ledger.transition(
                    action_id,
                    ExecutionState.PENDING_APPROVAL,
                    ExecutionState.APPROVED,
                ):
                    raise ValueError(
                        "Persistent approval state transition failed."
                    )

            try:
                self.manager.approve(action_id)
            except Exception as error:
                if self.ledger is not None:
                    restored = self.ledger.transition(
                        action_id,
                        ExecutionState.APPROVED,
                        ExecutionState.PENDING_APPROVAL,
                    )

                    if not restored:
                        raise RuntimeError(
                            "Approval failed and persistent state "
                            "could not be restored."
                        ) from error

                raise

    def reject(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "rejected")

            if self.ledger is not None:
                if not self.ledger.transition(
                    action_id,
                    ExecutionState.PENDING_APPROVAL,
                    ExecutionState.REJECTED,
                ):
                    raise ValueError(
                        "Persistent rejection state transition failed."
                    )

            try:
                self.manager.reject(action_id)
            except Exception as error:
                if self.ledger is not None:
                    restored = self.ledger.transition(
                        action_id,
                        ExecutionState.REJECTED,
                        ExecutionState.PENDING_APPROVAL,
                    )

                    if not restored:
                        raise RuntimeError(
                            "Rejection failed and persistent state "
                            "could not be restored."
                        ) from error

                raise
