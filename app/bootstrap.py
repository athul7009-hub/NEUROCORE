
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


def create_coordinator() -> Coordinator:
    """Build and initialize the NEUROCORE application."""

    # Initialize persistent memory.
    database = SQLiteDatabase(settings.database_path)
    repository = EpisodicMemoryRepository(database)
    memory_manager = MemoryManager(repository)
    memory_manager.initialize()

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
    )
