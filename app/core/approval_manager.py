import hashlib
import json
from uuid import UUID

from app.core.schemas import OperationPlan, OperationStatus


class ApprovalManager:

    def __init__(self):
        self.pending = {}
        self.approvals = {}
        self.operations = {}
        self.fingerprints = {}

    def generate_fingerprint(self, operation: OperationPlan) -> str:
        operation_data = operation.model_dump(
            mode="json",
            exclude={"status"},
        )

        serialized = json.dumps(
            operation_data,
            sort_keys=True,
            separators=(",", ":"),
        )

        return hashlib.sha256(
            serialized.encode("utf-8")
        ).hexdigest()

    def register(self, operation: OperationPlan):
        if operation.operation_id in self.operations:
            raise ValueError("Operation is already registered.")

        if operation.status != OperationStatus.PROPOSED:
            raise ValueError("Only proposed operations can be registered.")

        self.operations[operation.operation_id] = operation
        self.pending[operation.operation_id] = operation

    def approve(self, operation_id: UUID):
        operation = self.pending.get(operation_id)

        if operation is None:
            raise ValueError("Operation not found or already decided.")

        operation.status = OperationStatus.APPROVED

        self.approvals[operation_id] = True
        self.fingerprints[operation_id] = self.generate_fingerprint(operation)

        del self.pending[operation_id]

    def reject(self, operation_id: UUID):
        operation = self.pending.get(operation_id)

        if operation is None:
            raise ValueError("Operation not found or already decided.")

        operation.status = OperationStatus.REJECTED
        self.approvals[operation_id] = False

        del self.pending[operation_id]

    def is_authorized(self, operation_id: UUID) -> bool:
        if not self.approvals.get(operation_id, False):
            return False

        operation = self.operations.get(operation_id)

        if operation is None:
            return False

        if operation.status != OperationStatus.APPROVED:
            return False

        approved_fingerprint = self.fingerprints.get(operation_id)
        current_fingerprint = self.generate_fingerprint(operation)

        return approved_fingerprint == current_fingerprint