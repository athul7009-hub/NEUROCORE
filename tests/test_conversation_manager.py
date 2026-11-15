
from uuid import uuid4

import pytest

from app.llm.conversation_manager import ConversationManager


def test_creates_separate_conversations():
    manager = ConversationManager()

    first = manager.create_conversation()
    second = manager.create_conversation()

    assert first != second
    assert manager.get_history(first) == []
    assert manager.get_history(second) == []


def test_adds_and_retrieves_messages():
    manager = ConversationManager()
    conversation_id = manager.create_conversation()

    manager.add_message(conversation_id, "user", "Hello")
    manager.add_message(conversation_id, "assistant", "Hi!")

    history = manager.get_history(conversation_id)

    assert len(history) == 2
    assert history[0]["content"] == "Hello"
    assert history[1]["content"] == "Hi!"


def test_history_respects_message_limit():
    manager = ConversationManager(max_messages=2)
    conversation_id = manager.create_conversation()

    manager.add_message(conversation_id, "user", "One")
    manager.add_message(conversation_id, "assistant", "Two")
    manager.add_message(conversation_id, "user", "Three")

    history = manager.get_history(conversation_id)

    assert len(history) == 2
    assert history[0]["content"] == "Two"
    assert history[1]["content"] == "Three"


def test_conversations_are_isolated():
    manager = ConversationManager()

    first = manager.create_conversation()
    second = manager.create_conversation()

    manager.add_message(first, "user", "Private message")

    assert manager.get_history(second) == []


def test_rejects_invalid_role():
    manager = ConversationManager()
    conversation_id = manager.create_conversation()

    with pytest.raises(ValueError):
        manager.add_message(conversation_id, "system", "Invalid")


def test_rejects_empty_message():
    manager = ConversationManager()
    conversation_id = manager.create_conversation()

    with pytest.raises(ValueError):
        manager.add_message(conversation_id, "user", "  ")


def test_rejects_oversized_message():
    manager = ConversationManager(max_message_chars=5)
    conversation_id = manager.create_conversation()

    with pytest.raises(ValueError):
        manager.add_message(conversation_id, "user", "Too long")


def test_returns_independent_history_copy():
    manager = ConversationManager()
    conversation_id = manager.create_conversation()

    manager.add_message(conversation_id, "user", "Hello")

    history = manager.get_history(conversation_id)
    history.clear()

    assert len(manager.get_history(conversation_id)) == 1


def test_deletes_conversation():
    manager = ConversationManager()
    conversation_id = manager.create_conversation()

    manager.add_message(conversation_id, "user", "Hello")
    manager.delete_conversation(conversation_id)

    with pytest.raises(KeyError):
        manager.get_history(conversation_id)


def test_rejects_unknown_conversation():
    manager = ConversationManager()

    with pytest.raises(KeyError):
        manager.get_history(uuid4())

def test_history_respects_total_context_limit():
    manager = ConversationManager(
        max_context_chars=10,
    )
    conversation_id = manager.create_conversation()

    manager.add_message(conversation_id, "user", "123456")
    manager.add_message(conversation_id, "assistant", "abcdef")

    history = manager.get_history(conversation_id)

    assert history == [
        {"role": "assistant", "content": "abcdef"}
    ]


def test_rejects_invalid_context_limit():
    with pytest.raises(ValueError):
        ConversationManager(max_context_chars=0)
