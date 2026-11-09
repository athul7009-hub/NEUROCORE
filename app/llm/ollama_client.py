
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings


class OllamaError(Exception):
    """Base exception for Ollama communication errors."""


class OllamaConnectionError(OllamaError):
    """Raised when Ollama cannot be reached."""


class OllamaRequestError(OllamaError):
    """Raised when Ollama rejects a request."""


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an invalid response."""


class OllamaClient:
    """Handles communication with the local Ollama API."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int = 120,
    ):
        self.base_url = (
            base_url or settings.ollama_base_url
        ).rstrip("/")

        self.model = model or settings.ollama_model
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("Ollama base URL cannot be empty.")

        if not self.model:
            raise ValueError("Ollama model cannot be empty.")

        if timeout < 1:
            raise ValueError("Timeout must be at least 1 second.")

    def chat(
        self,
        messages: list[dict[str, str]],
        model: str | None = None,
        format: str | dict | None = None,
    ) -> str:
        """Send a chat request and return the model's response."""

        if not messages:
            raise ValueError("Messages cannot be empty.")

        for message in messages:
            if (
                not isinstance(message, dict)
                or not isinstance(message.get("role"), str)
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError(
                    "Each message must contain string role and content fields."
                )

        payload = {
            "model": model or self.model,
            "messages": messages,
            "stream": False,
        }

        if format is not None:
            payload["format"] = format

        request = Request(
            url=f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                result = json.loads(response.read().decode("utf-8"))

        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise OllamaRequestError(
                f"Ollama returned HTTP {exc.code}: {details[:500]}"
            ) from exc

        except (URLError, TimeoutError, OSError) as exc:
            raise OllamaConnectionError(
                f"Could not communicate with Ollama: {exc}"
            ) from exc

        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise OllamaResponseError(
                "Ollama returned invalid JSON."
            ) from exc

        if not isinstance(result, dict):
            raise OllamaResponseError(
                "Ollama response must be a JSON object."
            )

        message = result.get("message")

        if not isinstance(message, dict):
            raise OllamaResponseError(
                "Ollama response is missing its message object."
            )

        content = message.get("content")

        if not isinstance(content, str):
            raise OllamaResponseError(
                "Ollama response is missing valid message content."
            )

        return content.strip()
