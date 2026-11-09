
from app.memory.meta_schemas import MetaMemoryType


class MemoryIdentityPolicy:
    """Controls permission to inspect memory identities."""

    AUTHORIZED_AGENT = "CoordinatorAgent"
    ALLOWED_MEMORY_TYPES = frozenset(MetaMemoryType)

    @classmethod
    def authorize_inspection(
        cls,
        requesting_agent: str,
        memory_type: MetaMemoryType,
    ) -> None:
        if requesting_agent != cls.AUTHORIZED_AGENT:
            raise PermissionError(
                "Only the coordinator can inspect memory identities."
            )

        if memory_type not in cls.ALLOWED_MEMORY_TYPES:
            raise ValueError("Unsupported memory type.")
