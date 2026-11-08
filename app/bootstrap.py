
import sqlite3
from app.memory.repositories.working_memory import (
    WorkingMemoryRepository,
)
from app.memory.working_manager import WorkingMemoryManager
from app.agents.coordinator import Coordinator
from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.registry import AgentRegistry
from app.agents.verification_agent import VerificationAgent

from app.core.agent_auth import AgentAuthenticator
from app.core.config import settings

from app.memory.database import SQLiteDatabase
from app.memory.manager import MemoryManager
from app.memory.repositories.episodic_memory import (
    EpisodicMemoryRepository,
)
from app.memory.repositories.semantic_memory import (
    SemanticMemoryRepository,
)
from app.memory.semantic_manager import SemanticMemoryManager

from app.memory.repositories.procedural_memory import (
    ProceduralMemoryRepository,
)
from app.memory.procedural_manager import ProceduralMemoryManager


def create_coordinator() -> Coordinator:
    """Build and initialize the NEUROCORE application."""

    database = SQLiteDatabase(settings.database_path)

    database.database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    if not database.check_integrity():
        raise sqlite3.DatabaseError(
            "NEUROCORE memory database failed integrity check."
        )

    database.initialize()

    # Episodic memory.
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

    # Semantic memory.
    semantic_repository = SemanticMemoryRepository(database)
    semantic_memory_manager = SemanticMemoryManager(
        semantic_repository
    )
    semantic_memory_manager.initialize()

    # Procedural memory.
    procedural_repository = ProceduralMemoryRepository(database)
    procedural_memory_manager = ProceduralMemoryManager(
        procedural_repository
    )
    procedural_memory_manager.initialize()

    # Working memory.
    working_repository = WorkingMemoryRepository(database)
    working_memory_manager = WorkingMemoryManager(
        working_repository
    )
    working_memory_manager.initialize()
    # Register specialized agents.
    registry = AgentRegistry()
    registry.register(FileAnalysisAgent())
    registry.register(PlanningAgent())
    registry.register(VerificationAgent())

    # Configure agent authentication.
    authenticator = AgentAuthenticator({
        "FileAnalysisAgent": (
            settings.file_analysis_agent_key.get_secret_value()
        ),
        "PlanningAgent": (
            settings.planning_agent_key.get_secret_value()
        ),
        "VerificationAgent": (
            settings.verification_agent_key.get_secret_value()
        ),
    })

    return Coordinator(
        registry=registry,
        authenticator=authenticator,
        memory_manager=memory_manager,
        semantic_memory_manager=semantic_memory_manager,
        procedural_memory_manager=procedural_memory_manager,
        working_memory_manager=working_memory_manager,
    )
