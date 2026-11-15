
from app.llm.model_router import ModelRouter, TaskComplexity
from app.llm.ollama_client import OllamaClient
from uuid import UUID

from app.llm.conversation_manager import ConversationManager

class ChatService:
    """Handles ordinary conversations with a local LLM."""

    def __init__(
        self,
        client: OllamaClient | None = None,
        router: ModelRouter | None = None,
        conversation_manager: ConversationManager | None = None,
    ):
        self.client = client or OllamaClient()
        self.router = router or ModelRouter()
        self.conversation_manager = conversation_manager or ConversationManager()

    def chat(
        self,
        messages: list[dict[str, str]],
        complexity: TaskComplexity | None = None,
    ) -> str:
        """Generate a conversational response."""

        if complexity is None:
            complexity = self.router.classify(messages)

        route = self.router.route(complexity)

        return self.client.chat(
            messages,
            model=route["model"],
            think=route["think"],
        )
    def start_conversation(self) -> UUID:
        """Starts a new conversation."""
        return self.conversation_manager.create_conversation()



    def send_message(
        self,
        conversation_id: UUID,
        content: str,
        complexity: TaskComplexity | None = None,
    ) -> str:
        """Sends a message and saves history after a successful response."""

        history = self.conversation_manager.get_history(conversation_id)

        # Validate the new message before contacting the model.
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Message content cannot be empty.")

        if len(content) > self.conversation_manager.max_message_chars:
            raise ValueError("Message exceeds the maximum allowed length.")

        messages = history + [
            {"role": "user", "content": content.strip()}
        ]

        # Generate the response before changing stored history.
        response = self.chat(messages, complexity)

        # Save both messages only after successful generation.
        self.conversation_manager.add_message(
            conversation_id,
            "user",
            content,
        )
        self.conversation_manager.add_message(
            conversation_id,
            "assistant",
            response,
        )

        return response
