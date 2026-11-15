
import json
from uuid import uuid4

import pytest

from app.tools.tool_approval_audit import ToolApprovalAudit


def test_records_approval_without_sensitive_parameters(tmp_path):
    log_path = tmp_path / "approval.jsonl"
    audit = ToolApprovalAudit(log_path)
    action_id = uuid4()

    audit.record(
        action_id,
        "sample",
        "approved",
    )

    record = json.loads(log_path.read_text(encoding="utf-8"))

    assert record["action_id"] == str(action_id)
    assert record["tool_name"] == "sample"
    assert record["decision"] == "approved"
    assert record["decision_source"] == "local_cli"
    assert "parameters" not in record


def test_records_rejection(tmp_path):
    log_path = tmp_path / "approval.jsonl"
    audit = ToolApprovalAudit(log_path)

    audit.record(uuid4(), "sample", "rejected")

    record = json.loads(log_path.read_text(encoding="utf-8"))

    assert record["decision"] == "rejected"


def test_rejects_invalid_decision(tmp_path):
    audit = ToolApprovalAudit(tmp_path / "approval.jsonl")

    with pytest.raises(ValueError):
        audit.record(uuid4(), "sample", "executed")


def test_rejects_invalid_decision_source(tmp_path):
    audit = ToolApprovalAudit(tmp_path / "approval.jsonl")

    with pytest.raises(ValueError):
        audit.record(
            uuid4(),
            "sample",
            "approved",
            decision_source="agent",
        )
