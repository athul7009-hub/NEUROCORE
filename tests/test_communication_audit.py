

import json

import pytest

from app.core.communication_audit import CommunicationAudit
from app.core.schemas import AgentMessage, MessageType

from pathlib import Path
@pytest.fixture
def audit(tmp_path):
    log_path = tmp_path / "communication_audit.jsonl"
    return CommunicationAudit(log_path), log_path


def create_message(payload=None):
    return AgentMessage(
        task_id="12345678-1234-5678-1234-567812345678",
        sender="Coordinator",
        recipient="FileAnalysisAgent",
        message_type=MessageType.TASK,
        payload=payload if payload is not None else {
            "directory": "sample_project"
        },
    )


def read_records(log_path):
    return [
        json.loads(line)
        for line in log_path.read_text(encoding="utf-8").splitlines()
    ]


def test_records_accepted_communication(audit):
    logger, log_path = audit
    message = create_message()

    logger.record(message, "accepted")

    records = read_records(log_path)

    assert len(records) == 1
    assert records[0]["outcome"] == "accepted"
    assert records[0]["sender"] == "Coordinator"
    assert records[0]["recipient"] == "FileAnalysisAgent"


def test_records_rejected_communication(audit):
    logger, log_path = audit
    message = create_message()

    logger.record(message, "rejected", "Unauthorized field")

    record = read_records(log_path)[0]

    assert record["outcome"] == "rejected"
    assert record["reason"] == (
        "Communication policy validation failed."
    )


def test_records_field_names_without_payload_values(audit):
    logger, log_path = audit
    secret_value = "private-sensitive-value"

    message = create_message({
        "directory": secret_value,
    })

    logger.record(message, "accepted")

    log_contents = log_path.read_text(encoding="utf-8")

    assert "directory" in log_contents
    assert secret_value not in log_contents


def test_records_payload_size(audit):
    logger, log_path = audit
    message = create_message({"directory": "abc"})

    logger.record(message, "accepted")

    record = read_records(log_path)[0]

    assert record["payload_bytes"] == len(
        b'{"directory":"abc"}'
    )


def test_records_task_and_message_ids(audit):
    logger, log_path = audit
    message = create_message()

    logger.record(message, "accepted")

    record = read_records(log_path)[0]

    assert record["task_id"] == str(message.task_id)
    assert record["message_id"] == str(message.message_id)


def test_rejects_invalid_outcome(audit):
    logger, _ = audit
    message = create_message()

    with pytest.raises(ValueError, match="Invalid audit outcome"):
        logger.record(message, "unknown")


def test_multiple_events_are_appended(audit):
    logger, log_path = audit

    logger.record(create_message(), "accepted")
    logger.record(create_message(), "rejected", "Test rejection")

    records = read_records(log_path)

    assert len(records) == 2
    assert records[0]["outcome"] == "accepted"
    assert records[1]["outcome"] == "rejected"
def test_rejection_reason_does_not_contain_sensitive_values(audit):
    logger, log_path = audit

    secret = "private-sensitive-value"

    logger.record(
        create_message(),
        "rejected",
        "Communication policy validation failed.",
    )

    log_contents = log_path.read_text(encoding="utf-8")

    assert secret not in log_contents
    assert "Communication policy validation failed." in log_contents
def test_rejection_reason_is_sanitized(audit):
    logger, log_path = audit
    secret = "private-sensitive-value"

    logger.record(
        create_message(),
        "rejected",
        secret,
    )

    record = read_records(log_path)[0]

    assert record["reason"] == (
        "Communication policy validation failed."
    )
    assert secret not in log_path.read_text(encoding="utf-8")
def test_file_write_failure_propagates(audit, monkeypatch):
    logger, log_path = audit

    def fail_open(*args, **kwargs):
        raise OSError("Disk write failed")

    monkeypatch.setattr(Path, "open", fail_open)

    with pytest.raises(OSError, match="Disk write failed"):
        logger.record(create_message(), "accepted")