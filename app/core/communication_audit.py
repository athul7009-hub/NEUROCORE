
import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from app.core.schemas import AgentMessage


class CommunicationAudit:
    """
    Records agent communication metadata without storing payload contents.
    """

    def __init__(self, log_path: str | Path = "logs/communication_audit.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def record(
        self,
        message: AgentMessage,
        outcome: str,
        reason: str | None = None,
    ) -> None:
        if outcome not in {"accepted", "rejected"}:
            raise ValueError("Invalid audit outcome.")

        try:
            payload_bytes = len(
                json.dumps(
                    message.payload,
                    ensure_ascii=False,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode("utf-8")
            )
        except (TypeError, ValueError):
            payload_bytes = None

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "task_id": str(message.task_id),
            "message_id": str(message.message_id),
            "sender": message.sender,
            "recipient": message.recipient,
            "message_type": message.message_type.value,
            "shared_fields": sorted(message.payload.keys()),
            "payload_bytes": payload_bytes,
            "outcome": outcome,
            "reason": reason,
        }

        serialized_record = json.dumps(
            record,
            ensure_ascii=False,
            allow_nan=False,
        )

        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as log_file:
                log_file.write(serialized_record + "\n")
