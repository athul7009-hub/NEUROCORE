
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
        self._keys = {
            name: bytes.fromhex(key)
            for name, key in agent_keys.items()
            if key
        }

        if not self._keys:
            raise ValueError("At least one agent key is required.")

        if any(len(key) < 32 for key in self._keys.values()):
            raise ValueError("Agent keys must contain at least 32 bytes.")

        self.max_age = timedelta(seconds=max_age_seconds)
        self._seen_messages: set[str] = set()
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

    def verify(self, message: AgentMessage) -> bool:
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

        if not hmac.compare_digest(expected, message.signature):
            return False

        message_id = str(message.message_id)

        with self._lock:
            if message_id in self._seen_messages:
                return False

            self._seen_messages.add(message_id)

        return True
