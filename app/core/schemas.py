
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from app.memory.context_schemas import MemoryContext
from app.memory.semantic_context_schemas import SemanticMemoryContext


def current_timestamp() -> datetime:
    return datetime.now(timezone.utc)


# -------------------------------
# Message and operation types
# -------------------------------

class MessageType(str, Enum):
    TASK = "task"
    INFORMATION = "information"
    RESULT = "result"
    ERROR = "error"


class TaskIntent(str, Enum):
    FILE_ANALYSIS = "file_analysis"
    PLAN_TASK = "plan_task"


class ToolStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


class OperationAction(str, Enum):
    CREATE = "create"
    COPY = "copy"
    RENAME = "rename"
    QUARANTINE = "quarantine"
    RESTORE = "restore"


class OperationStatus(str, Enum):
    PROPOSED = "proposed"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"


# -------------------------------
# Incoming task schema
# -------------------------------

class TaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID = Field(default_factory=uuid4)
    user_input: str = Field(min_length=1, max_length=5000)
    intent: TaskIntent
    parameters: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=current_timestamp)


class TaskPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: UUID
    objective: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    requires_approval: bool = True
    created_at: datetime = Field(default_factory=current_timestamp)


# -------------------------------
# Agent communication schema
# -------------------------------

class AgentMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signature: str | None = None
    message_id: UUID = Field(default_factory=uuid4)
    task_id: UUID

    sender: str
    recipient: str
    message_type: MessageType

    payload: dict[str, Any] = Field(default_factory=dict)

    # Episodic memory context
    memory_context: MemoryContext | None = None

    # Validated semantic memory context
    semantic_context: SemanticMemoryContext | None = None

    in_reply_to: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    created_at: datetime = Field(default_factory=current_timestamp)

    priority: int = Field(default=5, ge=1, le=10)

    context_budget_tokens: int = Field(
        default=2000,
        ge=1,
        le=32000,
    )


# -------------------------------
# Proposed tool operation
# -------------------------------

class ToolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID = Field(default_factory=uuid4)

    tool_name: str
    parameters: dict[str, Any] = Field(default_factory=dict)

    requires_approval: bool = True
    dry_run: bool = True

    created_at: datetime = Field(default_factory=current_timestamp)


# -------------------------------
# Tool execution result
# -------------------------------

class ToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: UUID

    status: ToolStatus
    success: bool

    message: str

    data: dict[str, Any] = Field(default_factory=dict)

    completed_at: datetime = Field(default_factory=current_timestamp)


# -------------------------------
# File operation plan
# -------------------------------

class OperationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operation_id: UUID = Field(default_factory=uuid4)
    task_id: UUID
    action: OperationAction

    source_path: str | None = None
    destination_path: str

    # Quarantine management
    approved_root: str | None = None
    related_operation_id: UUID | None = None

    status: OperationStatus = OperationStatus.PROPOSED
    dry_run: bool = True
    requires_approval: bool = True

    created_at: datetime = Field(default_factory=current_timestamp)
    rollback_data: dict[str, Any] = Field(default_factory=dict)
