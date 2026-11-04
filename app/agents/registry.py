from app.agents.base_agent import BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        name = agent.name.strip()

        if not name:
            raise ValueError("Agent name cannot be empty.")

        if name in self._agents:
            raise ValueError(f"Agent '{name}' is already registered.")

        self._agents[name] = agent

    def get(self, name: str) -> BaseAgent:
        agent = self._agents.get(name)

        if agent is None:
            raise ValueError(f"Agent '{name}' is not registered.")

        return agent

    def list_agents(self) -> list[str]:
        return sorted(self._agents.keys())