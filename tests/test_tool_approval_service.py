
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

import pytest

from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_service import ToolApprovalService


class FakeApprovalManager:
    """Thread-safe manager for isolated service tests."""

    def __init__(self):
        self.pending = True
        self.decision = None
        self._lock = Lock()

    def get_pending_tool_name(self, action_id):
        with self._lock:
            if not self.pending:
                raise ValueError("Pending tool action not found.")
            return "sample"

    def approve(self, action_id):
        with self._lock:
            if not self.pending:
                raise ValueError("Pending tool action not found.")
            self.pending = False
            self.decision = "approved"

    def reject(self, action_id):
        with self._lock:
            if not self.pending:
                raise ValueError("Pending tool action not found.")
            self.pending = False
            self.decision = "rejected"


@pytest.fixture
def approval_setup(tmp_path):
    manager = FakeApprovalManager()
    audit = ToolApprovalAudit(tmp_path / "tool_approval_audit.jsonl")
    service = ToolApprovalService(manager, audit)

    return manager, audit, service


def read_audit(audit):
    return [
        json.loads(line)
        for line in audit.log_path.read_text(encoding="utf-8").splitlines()
    ]


def test_approval_creates_audit_record(approval_setup):
    manager, audit, service = approval_setup

    from uuid import uuid4
    action_id = uuid4()

    service.approve(action_id)

    records = read_audit(audit)

    assert manager.decision == "approved"
    assert len(records) == 1
    assert records[0]["action_id"] == str(action_id)
    assert records[0]["tool_name"] == "sample"
    assert records[0]["decision"] == "approved"


def test_rejection_creates_audit_record(approval_setup):
    manager, audit, service = approval_setup

    from uuid import uuid4
    action_id = uuid4()

    service.reject(action_id)

    records = read_audit(audit)

    assert manager.decision == "rejected"
    assert len(records) == 1
    assert records[0]["action_id"] == str(action_id)
    assert records[0]["decision"] == "rejected"


def test_audit_failure_prevents_approval(approval_setup, monkeypatch):
    manager, audit, service = approval_setup

    def fail_audit(*args, **kwargs):
        raise OSError("Audit storage unavailable.")

    monkeypatch.setattr(audit, "record", fail_audit)

    from uuid import uuid4

    with pytest.raises(OSError):
        service.approve(uuid4())

    assert manager.pending is True
    assert manager.decision is None


def test_concurrent_approval_and_rejection_allow_one_decision(
    approval_setup,
):
    manager, audit, service = approval_setup

    from uuid import uuid4
    action_id = uuid4()

    def approve():
        service.approve(action_id)

    def reject():
        service.reject(action_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(approve),
            executor.submit(reject),
        ]

        results = []

        for future in futures:
            try:
                future.result()
                results.append("success")
            except ValueError:
                results.append("rejected")

    records = read_audit(audit)

    assert results.count("success") == 1
    assert results.count("rejected") == 1
    assert manager.pending is False
    assert manager.decision in {"approved", "rejected"}
    assert len(records) == 1
    assert records[0]["decision"] == manager.decision
