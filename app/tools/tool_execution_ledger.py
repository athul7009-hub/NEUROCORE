
from enum import StrEnum

from app.memory.database import SQLiteDatabase


class ExecutionState(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERRUPTED = "interrupted"


class ToolExecutionLedger:
    """Persists tool execution state across application restarts."""

    ALLOWED_TRANSITIONS = {
        ExecutionState.PENDING_APPROVAL: {
            ExecutionState.APPROVED,
            ExecutionState.REJECTED,
            ExecutionState.EXECUTING,
        },
        ExecutionState.APPROVED: {
            ExecutionState.PENDING_APPROVAL,
            ExecutionState.EXECUTING,
        },
        ExecutionState.REJECTED: {
            ExecutionState.PENDING_APPROVAL,
        },
        ExecutionState.EXECUTING: {
            ExecutionState.COMPLETED,
            ExecutionState.FAILED,
            ExecutionState.INTERRUPTED,
        },
    }

    def __init__(self, database: SQLiteDatabase):
        self.database = database
        self.initialize()

    def initialize(self) -> None:
        """Creates or safely migrates the execution ledger."""

        with self.database.connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_execution_ledger (
                    action_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    fingerprint TEXT,
                    state TEXT NOT NULL,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

            columns = {
                row["name"]
                for row in connection.execute(
                    "PRAGMA table_info(tool_execution_ledger)"
                ).fetchall()
            }

            if "fingerprint" not in columns:
                connection.execute(
                    """
                    ALTER TABLE tool_execution_ledger
                    ADD COLUMN fingerprint TEXT
                    """
                )

            # Legacy records without fingerprints cannot be trusted
            # for safe request identity verification.
            connection.execute(
                """
                UPDATE tool_execution_ledger
                SET state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE fingerprint IS NULL
                """,
                (ExecutionState.INTERRUPTED.value,),
            )

    def recover_after_restart(self) -> None:
        """Recovers non-terminal states once during application startup."""

        with self.database.connection() as connection:
            # Approved actions return to pending approval because
            # in-memory approval decisions do not survive a restart.
            connection.execute(
                """
                UPDATE tool_execution_ledger
                SET state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE state = ?
                """,
                (
                    ExecutionState.PENDING_APPROVAL.value,
                    ExecutionState.APPROVED.value,
                ),
            )

            # An executing action has an uncertain outcome.
            # Never retry it automatically.
            connection.execute(
                """
                UPDATE tool_execution_ledger
                SET state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE state = ?
                """,
                (
                    ExecutionState.INTERRUPTED.value,
                    ExecutionState.EXECUTING.value,
                ),
            )

    def register(self, action_id, tool_name, fingerprint):
        """Registers an action or retrieves its existing state."""

        if not tool_name or not fingerprint:
            raise ValueError("Tool name and fingerprint must not be empty.")

        with self.database.connection() as connection:
            connection.execute(
                """
                INSERT INTO tool_execution_ledger (
                    action_id,
                    tool_name,
                    fingerprint,
                    state
                )
                VALUES (?, ?, ?, ?)
                ON CONFLICT(action_id) DO NOTHING
                """,
                (
                    str(action_id),
                    tool_name,
                    fingerprint,
                    ExecutionState.PENDING_APPROVAL.value,
                ),
            )

            row = connection.execute(
                """
                SELECT tool_name, fingerprint, state
                FROM tool_execution_ledger
                WHERE action_id = ?
                """,
                (str(action_id),),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Could not retrieve registered execution."
                )

            if (
                row["tool_name"] != tool_name
                or row["fingerprint"] != fingerprint
            ):
                raise ValueError(
                    "Action ID is already associated with another request."
                )

            try:
                return ExecutionState(row["state"])
            except ValueError as error:
                raise ValueError(
                    "Execution ledger contains an invalid state."
                ) from error

    def transition(self, action_id, expected, new_state):
        """Atomically transitions an action from its expected state."""

        if not isinstance(expected, ExecutionState):
            raise ValueError("Invalid expected execution state.")

        if not isinstance(new_state, ExecutionState):
            raise ValueError("Invalid new execution state.")

        if new_state not in self.ALLOWED_TRANSITIONS.get(expected, set()):
            raise ValueError(
                f"Invalid execution state transition: "
                f"{expected.value} -> {new_state.value}"
            )

        with self.database.connection() as connection:
            cursor = connection.execute(
                """
                UPDATE tool_execution_ledger
                SET state = ?, updated_at = CURRENT_TIMESTAMP
                WHERE action_id = ? AND state = ?
                """,
                (
                    new_state.value,
                    str(action_id),
                    expected.value,
                ),
            )

            return cursor.rowcount == 1

    def get_state(self, action_id):
        """Returns the current state of an action."""

        with self.database.connection() as connection:
            row = connection.execute(
                """
                SELECT state
                FROM tool_execution_ledger
                WHERE action_id = ?
                """,
                (str(action_id),),
            ).fetchone()

        if row is None:
            return None

        try:
            return ExecutionState(row["state"])
        except ValueError as error:
            raise ValueError(
                "Execution ledger contains an invalid state."
            ) from error
