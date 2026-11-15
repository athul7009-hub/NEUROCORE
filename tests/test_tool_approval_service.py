
import json
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_service import ToolApprovalService
from app.tools.tool_execution_ledger import (
    ExecutionState,
    ToolExecutionLedger,
)


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
@pytest.fixture
def persistent_approval_setup(tmp_path):
    database = SQLiteDatabase(tmp_path / "test.db")
    database.initialize()

    ledger = ToolExecutionLedger(database)
    manager = FakeApprovalManager()
    audit = ToolApprovalAudit(tmp_path / "persistent_audit.jsonl")
    service = ToolApprovalService(manager, audit, ledger)

    action_id = uuid4()
    ledger.register(action_id, "sample", "test-fingerprint")

    return manager, audit, service, ledger, action_id

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

from uuid import UUID

from app.tools.tool_approval_audit import ToolApprovalAudit
from app.tools.tool_approval_manager import ToolApprovalManager
from app.tools.tool_execution_ledger import (
    ExecutionState,
    ToolExecutionLedger,
)


class ToolApprovalService:
    """Coordinates audited and persistent approval decisions."""

    def __init__(
        self,
        manager: ToolApprovalManager,
        audit: ToolApprovalAudit,
        ledger: ToolExecutionLedger | None = None,
    ):
        self.manager = manager
        self.audit = audit
        self.ledger = ledger
        self._lock = Lock()

    def approve(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "approved")

            if self.ledger is not None:
                if not self.ledger.transition(
                    action_id,
                    ExecutionState.PENDING_APPROVAL,
                    ExecutionState.APPROVED,
                ):
                    raise ValueError(
                        "Persistent approval state transition failed."
                    )

            try:
                self.manager.approve(action_id)
            except Exception:
                if self.ledger is not None:
                    self.ledger.transition(
                        action_id,
                        ExecutionState.APPROVED,
                        ExecutionState.PENDING_APPROVAL,
                    )
                raise

    def reject(self, action_id: UUID) -> None:
        with self._lock:
            tool_name = self.manager.get_pending_tool_name(action_id)

            self.audit.record(action_id, tool_name, "rejected")

            if self.ledger is not None:
                if not self.ledger.transition(
                    action_id,
                    ExecutionState.PENDING_APPROVAL,
                    ExecutionState.REJECTED,
                ):
                    raise ValueError(
                        "Persistent rejection state transition failed."
                    )

            try:
                self.manager.reject(action_id)
            except Exception:
                if self.ledger is not None:
                    self.ledger.transition(
                        action_id,
                        ExecutionState.REJECTED,
                        ExecutionState.PENDING_APPROVAL,
                    )
                raise
def test_approval_persists_state(persistent_approval_setup):
    manager, audit, service, ledger, action_id = persistent_approval_setup

    service.approve(action_id)

    assert manager.decision == "approved"
    assert ledger.get_state(action_id) == ExecutionState.APPROVED


def test_rejection_persists_state(persistent_approval_setup):
    manager, audit, service, ledger, action_id = persistent_approval_setup

    service.reject(action_id)

    assert manager.decision == "rejected"
    assert ledger.get_state(action_id) == ExecutionState.REJECTED


def test_failed_persistent_transition_prevents_approval(
    persistent_approval_setup,
    monkeypatch,
):
    manager, audit, service, ledger, action_id = persistent_approval_setup

    def fail_transition(*args, **kwargs):
        return False

    monkeypatch.setattr(ledger, "transition", fail_transition)

    with pytest.raises(
        ValueError,
        match="Persistent approval state transition failed",
    ):
        service.approve(action_id)

    assert manager.pending is True
    assert manager.decision is None
def test_manager_approval_failure_restores_pending_ledger_state(
    persistent_approval_setup,
    monkeypatch,
):
    manager, audit, service, ledger, action_id = persistent_approval_setup

    def fail_approval(action_id):
        raise RuntimeError("Approval failed.")

    monkeypatch.setattr(manager, "approve", fail_approval)

    with pytest.raises(RuntimeError, match="Approval failed"):
        service.approve(action_id)

    assert ledger.get_state(action_id) == ExecutionState.PENDING_APPROVAL


def test_manager_rejection_failure_restores_pending_ledger_state(
    persistent_approval_setup,
    monkeypatch,
):
    manager, audit, service, ledger, action_id = persistent_approval_setup

    def fail_rejection(action_id):
        raise RuntimeError("Rejection failed.")

    monkeypatch.setattr(manager, "reject", fail_rejection)

    with pytest.raises(RuntimeError, match="Rejection failed"):
        service.reject(action_id)

    assert ledger.get_state(action_id) == ExecutionState.PENDING_APPROVAL