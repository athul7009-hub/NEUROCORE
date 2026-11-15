
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from uuid import UUID


class ToolApprovalAudit:
    """Records tool approval decisions without sensitive parameters."""

    VALID_DECISIONS = {"approved", "rejected"}

    def __init__(
        self,
        log_path: str | Path = "logs/tool_approval_audit.jsonl",
    ):
        self.log_path = Path(log_path)
        self._lock = Lock()

    def record(
        self,
        action_id: UUID,
        tool_name: str,
        decision: str,
        decision_source: str = "local_cli",
    ) -> None:
        if decision not in self.VALID_DECISIONS:
            raise ValueError("Invalid approval decision.")

        if not tool_name or not tool_name.strip():
            raise ValueError("Invalid tool name.")

        if decision_source != "local_cli":
            raise ValueError("Invalid decision source.")

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action_id": str(action_id),
            "tool_name": tool_name,
            "decision": decision,
            "decision_source": decision_source,
        }

        serialized = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
        )

        with self._lock:
            self.log_path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.log_path.open("a", encoding="utf-8") as file:
                file.write(serialized + "\n")
                file.flush()
