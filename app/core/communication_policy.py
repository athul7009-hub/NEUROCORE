
import json

from app.core.schemas import AgentMessage, MessageType


class CommunicationPolicy:
    """
    Controls which request payload fields an agent may receive.
    """

    def __init__(self, max_payload_bytes: int = 64 * 1024):
        if max_payload_bytes <= 0:
            raise ValueError("Payload limit must be positive.")

        self.max_payload_bytes = max_payload_bytes

        self.allowed_fields = {
            "FileAnalysisAgent": {
                "directory",
            },
            "PlanningAgent": {
                "objective",
            },
        }

    def validate_outgoing(self, message: AgentMessage) -> None:
        if message.message_type != MessageType.TASK:
            raise ValueError(
                "Communication policy only permits TASK requests."
            )

        if message.sender != "Coordinator":
            raise ValueError("Only the Coordinator may send task requests.")

        allowed = self.allowed_fields.get(message.recipient)

        if allowed is None:
            raise ValueError(
                f"No communication policy for {message.recipient}."
            )

        supplied_fields = set(message.payload.keys())
        unexpected_fields = supplied_fields - allowed

        if unexpected_fields:
            raise ValueError(
                "Unauthorized payload fields: "
                + ", ".join(sorted(unexpected_fields))
            )

        if not supplied_fields:
            raise ValueError("Task payload cannot be empty.")

        try:
            serialized = json.dumps(
                message.payload,
                ensure_ascii=False,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
        except (TypeError, ValueError) as error:
            raise ValueError("Payload must contain valid JSON data.") from error

        if len(serialized) > self.max_payload_bytes:
            raise ValueError(
                f"Payload exceeds the {self.max_payload_bytes}-byte limit."
            )
