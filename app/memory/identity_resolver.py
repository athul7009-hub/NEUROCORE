
from uuid import UUID

from app.memory.identity_policy import MemoryIdentityPolicy
from app.memory.identity_schemas import (
    MemoryIdentityAssessment,
    MemoryIdentityAvailability,
    MemoryIdentityRequest,
)
from app.memory.meta_schemas import MetaMemoryType


class MemoryIdentityResolver:
    """Resolves memory identities through authorized memory managers."""

    def __init__(
        self,
        *,
        episodic_manager,
        semantic_manager,
        procedural_manager,
        working_manager,
        prospective_manager,
        policy: MemoryIdentityPolicy | None = None,
    ):
        self.managers = {
            MetaMemoryType.EPISODIC: episodic_manager,
            MetaMemoryType.SEMANTIC: semantic_manager,
            MetaMemoryType.PROCEDURAL: procedural_manager,
            MetaMemoryType.WORKING: working_manager,
            MetaMemoryType.PROSPECTIVE: prospective_manager,
        }
        self.policy = policy or MemoryIdentityPolicy()

    def inspect(
        self,
        request: MemoryIdentityRequest,
        *,
        requesting_agent: str,
    ) -> MemoryIdentityAssessment:
        """Inspects one memory identity without retrieving its content."""

        if not isinstance(request, MemoryIdentityRequest):
            raise TypeError("Expected a MemoryIdentityRequest.")

        # Authorize before accessing any manager.
        self.policy.authorize_inspection(
            requesting_agent,
            request.memory_type,
        )

        manager = self.managers[request.memory_type]

        if request.memory_type == MetaMemoryType.WORKING:
            return manager.inspect_identity(
                request.memory_id,
                request.task_id,
                requesting_agent=requesting_agent,
            )

        if request.memory_type == MetaMemoryType.PROSPECTIVE:
            return manager.inspect_identity(
                request.memory_id,
                requesting_agent=requesting_agent,
            )

        status = manager.inspect_identity(
            request.memory_id,
            requesting_agent=requesting_agent,
        )

        return self._build_assessment(
            request.memory_type,
            request.memory_id,
            status,
        )

    @staticmethod
    def _build_assessment(
        memory_type: MetaMemoryType,
        memory_id: UUID,
        status,
    ) -> MemoryIdentityAssessment:
        """Converts manager lifecycle status into a common assessment."""

        if status is None:
            return MemoryIdentityAssessment(
                memory_type=memory_type,
                memory_id=memory_id,
                exists=False,
                lifecycle_status=None,
                availability=MemoryIdentityAvailability.NOT_FOUND,
            )

        lifecycle_status = status.value

        availability_by_type = {
            MetaMemoryType.EPISODIC: {
                "active": MemoryIdentityAvailability.AVAILABLE,
                "archived": MemoryIdentityAvailability.INACTIVE,
            },
            MetaMemoryType.SEMANTIC: {
                "validated": MemoryIdentityAvailability.AVAILABLE,
                "deprecated": MemoryIdentityAvailability.INACTIVE,
                "candidate": MemoryIdentityAvailability.UNAVAILABLE,
            },
            MetaMemoryType.PROCEDURAL: {
                "validated": MemoryIdentityAvailability.AVAILABLE,
                "deprecated": MemoryIdentityAvailability.INACTIVE,
                "candidate": MemoryIdentityAvailability.UNAVAILABLE,
            },
        }

        availability = availability_by_type[memory_type].get(
            lifecycle_status,
            MemoryIdentityAvailability.UNAVAILABLE,
        )

        return MemoryIdentityAssessment(
            memory_type=memory_type,
            memory_id=memory_id,
            exists=True,
            lifecycle_status=lifecycle_status,
            availability=availability,
        )
