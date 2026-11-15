
import hashlib
import json
from threading import Lock
from uuid import UUID

from app.core.schemas import ToolRequest
from app.tools.tool_schemas import ToolDefinition


class ToolApprovalManager:
    """Manages explicit, thread-safe, fingerprint-bound approvals."""

    def __init__(self):
        self._pending: dict[UUID, str] = {}
        self._approved: dict[UUID, str] = {}
        self._rejected: set[UUID] = set()
        self._consumed: set[UUID] = set()
        self._lock = Lock()
        self._pending_tool_names: dict[UUID, str] = {}

    def _generate_fingerprint(
        self,
        request: ToolRequest,
        tool: ToolDefinition,

    ) -> str:
        handler = tool.handler

        handler_module = getattr(handler, "__module__", None)
        handler_name = getattr(handler, "__qualname__", None)

        if not isinstance(handler_module, str):
            handler_module = type(handler).__module__

        if not isinstance(handler_name, str):
            handler_name = type(handler).__qualname__
        data = {
            "request": request.model_dump(mode="json"),
            "tool": {
                "version": tool.version,
                "handler": f"{handler_module}.{handler_name}",
                "name": tool.name,
                "requires_approval": tool.requires_approval,
                "read_only": tool.read_only,
                "input_schema_definition": (
                    tool.input_schema.model_json_schema()
                ),
                "output_schema_definition": (
                    tool.output_schema.model_json_schema()
                ),
                "input_schema_type": (
                    f"{tool.input_schema.__module__}."
                    f"{tool.input_schema.__qualname__}"
                ),
                "output_schema_type": (
                    f"{tool.output_schema.__module__}."
                    f"{tool.output_schema.__qualname__}"
                ),
            },
        }

        serialized = json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def register(
        self,
        request: ToolRequest,
        tool: ToolDefinition,
    ) -> None:
        if request.tool_name != tool.name:
            raise ValueError("Tool request and definition do not match.")

        if not tool.requires_approval:
            raise ValueError("This tool does not require approval.")

        fingerprint = self._generate_fingerprint(request, tool)
        action_id = request.action_id


        with self._lock:
            if (
                action_id in self._pending
                or action_id in self._approved
                or action_id in self._rejected
                or action_id in self._consumed
            ):
                raise ValueError("Tool action is already registered.")

            self._pending[action_id] = fingerprint
            self._pending_tool_names[action_id] = tool.name

    def approve(self, action_id: UUID) -> None:
        with self._lock:
            fingerprint = self._pending.pop(action_id, None)

            if fingerprint is None:
                raise ValueError("Pending tool action not found.")

            self._approved[action_id] = fingerprint
            self._pending_tool_names.pop(action_id, None)
    def reject(self, action_id: UUID) -> None:
        with self._lock:
            if action_id not in self._pending:
                raise ValueError("Pending tool action not found.")

            del self._pending[action_id]
            self._rejected.add(action_id)
            self._pending_tool_names.pop(action_id, None)
    def consume_approval(
        self,
        request: ToolRequest,
        tool: ToolDefinition,
    ) -> bool:
        current_fingerprint = self._generate_fingerprint(
            request,
            tool,
        )
        action_id = request.action_id

        with self._lock:
            approved_fingerprint = self._approved.pop(
                action_id,
                None,
            )

            if approved_fingerprint is None:
                return False

            # Consume even when fingerprint validation fails.
            self._consumed.add(action_id)

            return approved_fingerprint == current_fingerprint

    def is_pending(self, action_id: UUID) -> bool:
        with self._lock:
            return action_id in self._pending

    def is_approved(self, action_id: UUID) -> bool:
        with self._lock:
            return action_id in self._approved

    def is_rejected(self, action_id: UUID) -> bool:
        with self._lock:
            return action_id in self._rejected

    def is_consumed(self, action_id: UUID) -> bool:
        with self._lock:
            return action_id in self._consumed
    def get_pending_tool_name(self, action_id: UUID) -> str:
        with self._lock:
            tool_name = self._pending_tool_names.get(action_id)

            if tool_name is None:
                raise ValueError("Pending tool action not found.")

            return tool_name