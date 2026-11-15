import pytest
from unittest.mock import Mock

from app.llm.chat_service import ChatService
from app.llm.model_router import TaskComplexity


def test_chat_uses_simple_routing():
    client = Mock()
    client.chat.return_value = "Hello!"

    service = ChatService(client=client)

    result = service.chat([
        {"role": "user", "content": "Hello"}
    ])

    assert result == "Hello!"
    client.chat.assert_called_once_with(
        [{"role": "user", "content": "Hello"}],
        model=service.router.default_model,
        think=False,
    )


def test_chat_uses_complex_routing():
    client = Mock()
    client.chat.return_value = "Detailed answer."

    service = ChatService(client=client)

    service.chat(
        [{"role": "user", "content": "Explain neural networks."}],
        complexity=TaskComplexity.COMPLEX,
    )

    client.chat.assert_called_once_with(
        [{"role": "user", "content": "Explain neural networks."}],
        model=service.router.default_model,
        think=True,
    )

def test_starts_conversation():
    service = ChatService()

    conversation_id = service.start_conversation()

    assert conversation_id is not None
    assert service.conversation_manager.get_history(conversation_id) == []


def test_send_message_uses_and_updates_conversation_history():
    client = Mock()
    client.chat.return_value = "Hello! How can I help?"

    service = ChatService(client=client)
    conversation_id = service.start_conversation()

    response = service.send_message(conversation_id, "Hello")

    assert response == "Hello! How can I help?"

    history = service.conversation_manager.get_history(conversation_id)

    assert history == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello! How can I help?"},
    ]


def test_send_message_preserves_previous_context():
    client = Mock()
    client.chat.side_effect = ["Hello!", "Python is a programming language."]

    service = ChatService(client=client)
    conversation_id = service.start_conversation()

    service.send_message(conversation_id, "Hello")
    service.send_message(conversation_id, "What is Python?")

    second_call_messages = client.chat.call_args_list[1].args[0]

    assert second_call_messages == [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hello!"},
        {"role": "user", "content": "What is Python?"},
    ]

def test_failed_model_request_does_not_modify_history():
    client = Mock()
    client.chat.side_effect = RuntimeError("Ollama unavailable")

    service = ChatService(client=client)
    conversation_id = service.start_conversation()

    service.conversation_manager.add_message(
        conversation_id,
        "user",
        "Previous message",
    )

    original_history = service.conversation_manager.get_history(
        conversation_id
    )

    with pytest.raises(RuntimeError, match="Ollama unavailable"):
        service.send_message(conversation_id, "New message")

    assert service.conversation_manager.get_history(
        conversation_id
    ) == original_history
