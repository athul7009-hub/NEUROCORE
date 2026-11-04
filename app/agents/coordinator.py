
from app.agents.registry import AgentRegistry
from app.core.schemas import (
    AgentMessage,
    MessageType,
    TaskIntent,
    TaskRequest,
)


class Coordinator:
    def __init__(self, registry: AgentRegistry):
        self.registry = registry

        self.routes = {
            TaskIntent.FILE_ANALYSIS: "FileAnalysisAgent",
            TaskIntent.PLAN_TASK: "PlanningAgent",
        }

    def handle_task(self, task: TaskRequest) -> AgentMessage:
        try:
            agent_name = self.routes.get(task.intent)

            if agent_name is None:
                raise ValueError(
                    f"Unsupported task intent: {task.intent}"
                )

            if task.intent == TaskIntent.FILE_ANALYSIS:
                directory = task.parameters.get("directory")

                if not isinstance(directory, str) or not directory.strip():
                    raise ValueError(
                        "A valid directory parameter is required."
                    )

                payload = {"directory": directory}

            elif task.intent == TaskIntent.PLAN_TASK:
                payload = {"objective": task.user_input}

            agent = self.registry.get(agent_name)

            message = AgentMessage(
                task_id=task.task_id,
                sender="Coordinator",
                recipient=agent_name,
                message_type=MessageType.TASK,
                payload=payload,
            )

            return agent.process(message)

        except ValueError as error:
            return AgentMessage(
                task_id=task.task_id,
                sender="Coordinator",
                recipient="User",
                message_type=MessageType.ERROR,
                payload={"error": str(error)},
            )
