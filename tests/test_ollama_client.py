
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

def test_chat_disables_thinking_when_requested(client):
    response_data = {
        "message": {
            "role": "assistant",
            "content": "Python is a programming language.",
        }
    }

    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(json.dumps(response_data).encode()),
    ) as mock_urlopen:
        client.chat(
            [{"role": "user", "content": "What is Python?"}],
            think=False,
        )

    request = mock_urlopen.call_args.args[0]
    payload = json.loads(request.data)

    assert payload["think"] is False


def test_chat_enables_thinking_when_requested(client):
    response_data = {
        "message": {
            "role": "assistant",
            "content": "Here is my reasoning.",
        }
    }

    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(json.dumps(response_data).encode()),
    ) as mock_urlopen:
        client.chat(
            [{"role": "user", "content": "Solve this problem."}],
            think=True,
        )

    request = mock_urlopen.call_args.args[0]
    payload = json.loads(request.data)

    assert payload["think"] is True


def test_chat_omits_think_when_not_specified(client):
    response_data = {
        "message": {
            "role": "assistant",
            "content": "Hello!",
        }
    }

    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(json.dumps(response_data).encode()),
    ) as mock_urlopen:
        client.chat([{"role": "user", "content": "Hello"}])

    request = mock_urlopen.call_args.args[0]
    payload = json.loads(request.data)

    assert "think" not in payload


def test_chat_rejects_invalid_think_value(client):
    with pytest.raises(ValueError, match="Think must be a boolean"):
        client.chat(
            [{"role": "user", "content": "Hello"}],
            think="false",
        )
def test_list_models_returns_installed_models(client):
    response_data = {
        "models": [
            {"name": "qwen3:8b"},
            {"name": "llama3:latest"},
        ]
    }

    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(json.dumps(response_data).encode()),
    ):
        assert client.list_models() == [
            "qwen3:8b",
            "llama3:latest",
        ]


def test_list_models_handles_connection_failure(client):
    with patch(
        "app.llm.ollama_client.urlopen",
        side_effect=URLError("Connection refused"),
    ):
        with pytest.raises(OllamaConnectionError):
            client.list_models()


def test_list_models_rejects_invalid_response(client):
    with patch(
        "app.llm.ollama_client.urlopen",
        return_value=BytesIO(b"invalid json"),
    ):
        with pytest.raises(OllamaResponseError):
            client.list_models()