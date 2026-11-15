
from uuid import UUID, uuid4


class ConversationManager:
    """Manages isolated, short-term conversation histories."""

    def __init__(
        self,
        max_messages: int = 20,
        max_message_chars: int = 12000,
        max_context_chars: int = 24000,

    ):
        if max_messages < 1:
            raise ValueError("Maximum messages must be at least 1.")

        if max_message_chars < 1:
            raise ValueError("Maximum message length must be at least 1.")
        if max_context_chars < 1:
            raise ValueError("Maximum context length must be at least 1.")

        self.max_messages = max_messages
        self.max_message_chars = max_message_chars
        self.max_context_chars = max_context_chars
        self._conversations: dict[UUID, list[dict[str, str]]] = {}

    def create_conversation(self) -> UUID:
        conversation_id = uuid4()
        self._conversations[conversation_id] = []
        return conversation_id

    def add_message(
        self,
        conversation_id: UUID,
        role: str,
        content: str,
    ) -> None:
        if conversation_id not in self._conversations:
            raise KeyError("Conversation does not exist.")

        if role not in ("user", "assistant"):
            raise ValueError("Invalid conversation message role.")

        if not isinstance(content, str) or not content.strip():
            raise ValueError("Message content cannot be empty.")

        if len(content) > self.max_message_chars:
            raise ValueError("Message exceeds the maximum allowed length.")

        history = self._conversations[conversation_id]

        history.append({
            "role": role,
            "content": content.strip(),
        })

        while history and (
            len(history) > self.max_messages
            or sum(len(message["content"]) for message in history)
            > self.max_context_chars
        ):
            history.pop(0)

    def get_history(
        self,
        conversation_id: UUID,
    ) -> list[dict[str, str]]:
        if conversation_id not in self._conversations:
            raise KeyError("Conversation does not exist.")

        return [
            message.copy()
            for message in self._conversations[conversation_id]
        ]

    def delete_conversation(self, conversation_id: UUID) -> None:
        if conversation_id not in self._conversations:
            raise KeyError("Conversation does not exist.")

        del self._conversations[conversation_id]
