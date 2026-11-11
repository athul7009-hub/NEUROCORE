
import json

from app.core.schemas import AgentMessage, MessageType


class CommunicationPolicy:
    """
    Controls which request payload fields and memory contexts
    an agent may receive.
    """

    CONTEXT_FIELDS = (
        "memory_context",
        "semantic_context",
        "procedural_context",
        "working_memory_context",
        "prospective_context",
    )

    def __init__(self, max_payload_bytes: int = 64 * 1024):
        if (
            not isinstance(max_payload_bytes, int)
            or isinstance(max_payload_bytes, bool)
            or max_payload_bytes <= 0
        ):
            raise ValueError("Payload limit must be a positive integer.")

        self.max_payload_bytes = max_payload_bytes

        self.allowed_fields = {
            "FileAnalysisAgent": {"directory"},
            "PlanningAgent": {"objective"},
            "VerificationAgent": {"planning_result"},
        }

        self.allowed_contexts = {
            "FileAnalysisAgent": set(),
            "PlanningAgent": set(self.CONTEXT_FIELDS),
            "VerificationAgent": set(self.CONTEXT_FIELDS),
        }

    def validate_outgoing(self, message: AgentMessage) -> None:
        if message.message_type != MessageType.TASK:
            raise ValueError(
                "Communication policy only permits TASK requests."
            )

        if message.sender != "Coordinator":
            raise ValueError(
                "Only the Coordinator may send task requests."
            )

        allowed = self.allowed_fields.get(message.recipient)

        if allowed is None:
            raise ValueError(
                f"No communication policy for {message.recipient}."
            )

        # Validate memory context permissions and isolation.
        allowed_contexts = self.allowed_contexts[message.recipient]

        for field in self.CONTEXT_FIELDS:
            context = getattr(message, field)

            if context is None:
                continue

            if field not in allowed_contexts:
                raise ValueError(
                    f"Unauthorized memory context: {field}."
                )

            if context.task_id != message.task_id:
                raise ValueError(
                    f"{field} task ID mismatch."
                )

            if context.recipient_agent != message.recipient:
                raise ValueError(
                    f"{field} recipient mismatch."
                )

        # Validate ordinary payload fields.
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
            raise ValueError(
                "Payload must contain valid JSON data."
            ) from error

        if len(serialized) > self.max_payload_bytes:
            raise ValueError(
                f"Payload exceeds the {self.max_payload_bytes}-byte limit."
            )
