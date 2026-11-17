
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone
from threading import Lock

from app.core.schemas import AgentMessage


class AgentAuthenticator:
    def __init__(
        self,
        agent_keys: dict[str, str],
        max_age_seconds: int = 300,
    ):
        if (
            not isinstance(max_age_seconds, int)
            or isinstance(max_age_seconds, bool)
            or max_age_seconds <= 0
        ):
            raise ValueError("Maximum message age must be a positive integer.")
        self._keys = {}

        for name, key in agent_keys.items():
            if not name.strip():
                raise ValueError("Agent identity cannot be empty.")

            if not key:
                raise ValueError(f"Authentication key for '{name}' is missing.")

            try:
                decoded_key = bytes.fromhex(key)
            except ValueError as exc:
                raise ValueError(
                    f"Authentication key for '{name}' must be valid hexadecimal."
                ) from exc

            if len(decoded_key) < 32:
                raise ValueError(
                    f"Authentication key for '{name}' must contain at least 32 bytes."
                )

            self._keys[name] = decoded_key

        if not self._keys:
            raise ValueError("At least one agent key is required.")

        if any(len(key) < 32 for key in self._keys.values()):
            raise ValueError("Agent keys must contain at least 32 bytes.")

        self.max_age = timedelta(seconds=max_age_seconds)
        self._seen_messages: dict[str, datetime] = {}
        self._lock = Lock()

    @staticmethod
    def _canonical_message(message: AgentMessage) -> bytes:
        data = message.model_dump(
            mode="json",
            exclude={"signature"},
        )
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    def sign(
        self,
        message: AgentMessage,
        expected_sender: str,
    ) -> AgentMessage:
        if not isinstance(message, AgentMessage):
            raise TypeError("Only AgentMessage instances can be signed.")

        if message.sender != expected_sender:
            raise ValueError("Agent identity does not match the sender.")

        key = self._keys.get(expected_sender)
        if key is None:
            raise ValueError("Unknown agent identity.")

        unsigned = message.model_copy(update={"signature": None})
        digest = hmac.new(
            key,
            self._canonical_message(unsigned),
            hashlib.sha256,
        ).hexdigest()

        return unsigned.model_copy(update={"signature": digest})
    def verify_signature(self, message: AgentMessage) -> bool:
        if not isinstance(message, AgentMessage):
            return False

        key = self._keys.get(message.sender)

        if key is None or not message.signature:
            return False

        now = datetime.now(timezone.utc)
        timestamp = message.created_at

        if timestamp.tzinfo is None:
            return False

        if now - timestamp > self.max_age:
            return False

        if timestamp - now > self.max_age:
            return False

        unsigned = message.model_copy(update={"signature": None})
        expected = hmac.new(
            key,
            self._canonical_message(unsigned),
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected, message.signature)

    def verify(self, message: AgentMessage) -> bool:
        if not self.verify_signature(message):
            return False

        now = datetime.now(timezone.utc)
        message_id = str(message.message_id)
        expires_at = message.created_at + self.max_age

        with self._lock:
            expired_ids = [
                cached_id
                for cached_id, expiry in self._seen_messages.items()
                if expiry < now
            ]

            for cached_id in expired_ids:
                del self._seen_messages[cached_id]

            if message_id in self._seen_messages:
                return False

            self._seen_messages[message_id] = expires_at

        return True