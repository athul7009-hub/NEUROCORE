
from uuid import uuid4

import pytest

from app.memory.database import SQLiteDatabase
from app.tools.tool_execution_ledger import (
    ExecutionState,
    ToolExecutionLedger,
)


@pytest.fixture
def database(tmp_path):
    db = SQLiteDatabase(tmp_path / "test_neurocore.db")
    db.initialize()
    return db


@pytest.fixture
def ledger(database):
    return ToolExecutionLedger(database)


def register_action(ledger):
    action_id = uuid4()
    ledger.register(
        action_id,
        "test_tool",
        "test_fingerprint",
    )
    return action_id


def test_pending_approval_survives_restart(database, ledger):
    action_id = register_action(ledger)

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.PENDING_APPROVAL
    )


def test_approved_action_requires_fresh_approval_after_restart(
    database,
    ledger,
):
    action_id = register_action(ledger)

    assert ledger.transition(
        action_id,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.APPROVED,
    )

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.PENDING_APPROVAL
    )


def test_executing_action_becomes_interrupted_after_restart(
    database,
    ledger,
):
    action_id = register_action(ledger)

    assert ledger.transition(
        action_id,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.EXECUTING,
    )

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.INTERRUPTED
    )


def test_completed_action_remains_completed_after_restart(
    database,
    ledger,
):
    action_id = register_action(ledger)

    assert ledger.transition(
        action_id,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.EXECUTING,
    )

    assert ledger.transition(
        action_id,
        ExecutionState.EXECUTING,
        ExecutionState.COMPLETED,
    )

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.COMPLETED
    )


def test_failed_action_remains_failed_after_restart(
    database,
    ledger,
):
    action_id = register_action(ledger)

    assert ledger.transition(
        action_id,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.EXECUTING,
    )

    assert ledger.transition(
        action_id,
        ExecutionState.EXECUTING,
        ExecutionState.FAILED,
    )

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.FAILED
    )


def test_rejected_action_remains_rejected_after_restart(
    database,
    ledger,
):
    action_id = register_action(ledger)

    assert ledger.transition(
        action_id,
        ExecutionState.PENDING_APPROVAL,
        ExecutionState.REJECTED,
    )

    restarted_ledger = ToolExecutionLedger(database)
    restarted_ledger.recover_after_restart()

    assert (
        restarted_ledger.get_state(action_id)
        == ExecutionState.REJECTED
    )


def test_action_id_cannot_be_reused_with_different_fingerprint(ledger):
    action_id = register_action(ledger)

    with pytest.raises(
        ValueError,
        match="already associated",
    ):
        ledger.register(
            action_id,
            "test_tool",
            "different_fingerprint",
        )


def test_invalid_state_transition_is_rejected(ledger):
    action_id = register_action(ledger)

    with pytest.raises(ValueError, match="Invalid execution state"):
        ledger.transition(
            action_id,
            ExecutionState.PENDING_APPROVAL,
            ExecutionState.COMPLETED,
        )


def test_concurrent_transition_only_succeeds_once(ledger):
    action_id = register_action(ledger)

    results = [
        ledger.transition(
            action_id,
            ExecutionState.PENDING_APPROVAL,
            ExecutionState.EXECUTING,
        )
        for _ in range(2)
    ]

    assert results == [True, False]


def test_legacy_records_without_fingerprint_are_interrupted(database):
    with database.connection() as connection:
        connection.execute(
            """
            CREATE TABLE tool_execution_ledger (
                action_id TEXT PRIMARY KEY,
                tool_name TEXT NOT NULL,
                state TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        action_id = str(uuid4())

        connection.execute(
            """
            INSERT INTO tool_execution_ledger (
                action_id,
                tool_name,
                state
            )
            VALUES (?, ?, ?)
            """,
            (
                action_id,
                "legacy_tool",
                ExecutionState.PENDING_APPROVAL.value,
            ),
        )

    migrated_ledger = ToolExecutionLedger(database)

    assert (
        migrated_ledger.get_state(__import__("uuid").UUID(action_id))
        == ExecutionState.INTERRUPTED
    )
