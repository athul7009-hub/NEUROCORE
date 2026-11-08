
import json
from io import BytesIO
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import pytest

from app.llm.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaRequestError,
    OllamaResponseError,
)


@pytest.fixture
def client():
    return OllamaClient(
        base_url="http://localhost:11434",
        model="qwen3:8b",
    )


def test_chat_returns_model_response(client):
    response_data = {
        "message": {
            "role": "assistant",
            "content": "Hello from Qwen!",
        }
    }

    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(json.dumps(response_data).encode()),
    ):
        result = client.chat([
            {"role": "user", "content": "Hello"}
        ])

    assert result == "Hello from Qwen!"


def test_chat_rejects_empty_messages(client):
    with pytest.raises(ValueError):
        client.chat([])


def test_chat_handles_connection_failure(client):
    with patch(
        "app.llm.ollama_client.urlopen",
        side_effect=URLError("Connection refused"),
    ):
        with pytest.raises(OllamaConnectionError):
            client.chat([
                {"role": "user", "content": "Hello"}
            ])


def test_chat_handles_http_error(client):
    error = HTTPError(
        url="http://localhost:11434/api/chat",
        code=500,
        msg="Server error",
        hdrs=None,
        fp=BytesIO(b"Internal server error"),
    )

    with patch(
        "app.llm.ollama_client.urlopen",
        side_effect=error,
    ):
        with pytest.raises(OllamaRequestError):
            client.chat([
                {"role": "user", "content": "Hello"}
            ])


def test_chat_rejects_invalid_response(client):
    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(b"invalid json"),
    ):
        with pytest.raises(OllamaResponseError):
            client.chat([
                {"role": "user", "content": "Hello"}
            ])


def test_chat_rejects_missing_message(client):
    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(b'{"model": "qwen3:8b"}'),
    ):
        with pytest.raises(OllamaResponseError):
            client.chat([
                {"role": "user", "content": "Hello"}
            ])
