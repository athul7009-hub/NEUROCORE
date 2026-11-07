from app.bootstrap import create_coordinator

from app.agents.file_analysis_agent import FileAnalysisAgent
from app.agents.planning_agent import PlanningAgent
from app.agents.verification_agent import VerificationAgent


def test_create_coordinator_initializes_application():
    coordinator = create_coordinator()

    assert coordinator is not None
    assert coordinator.memory_manager is not None

    agents = coordinator.registry.list_agents()

    assert agents == [
        "FileAnalysisAgent",
        "PlanningAgent",
        "VerificationAgent",
    ]

    assert isinstance(
        coordinator.registry.get("FileAnalysisAgent"),
        FileAnalysisAgent,
    )
    assert isinstance(
        coordinator.registry.get("PlanningAgent"),
        PlanningAgent,
    )
    assert isinstance(
        coordinator.registry.get("VerificationAgent"),
        VerificationAgent,
    )