
from threading import Lock
from uuid import UUID

from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_manager import ToolApprovalManager


class ToolApprovalService:
    """Coordinates audited approval and rejection decisions."""

    def __init__(
        self,
        manager: ToolApprovalManager,
        audit: ToolApprovalAudit,
    ):
        self.manager = manager
        self.audit = audit
        self._lock = Lock()

    def approve(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "approved")
            self.manager.approve(action_id)

    def reject(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "rejected")
            self.manager.reject(action_id)