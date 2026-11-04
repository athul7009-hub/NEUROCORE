from app.agents.base_agent import BaseAgent
from app.core.schemas import AgentMessage, MessageType
from app.tools.scan_pipeline import run_scan


class FileAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            name="FileAnalysisAgent",
            description="Scans approved directories and analyzes file metadata."
        )

    def process(self, message: AgentMessage) -> AgentMessage:
        try:
            directory = message.payload.get("directory")

            if not isinstance(directory, str) or not directory.strip():
                raise ValueError("A valid directory must be provided.")

            result = run_scan(directory)

            summary = {
                "root": result["root"],
                "total_files": result["total_files"],
                "total_size_bytes": result["total_size_bytes"],
                "extension_counts": result["extension_counts"],
                "duplicate_groups": len(result["duplicates"]),
                "recoverable_bytes_estimate": result["recoverable_bytes"],
                "scan_warnings": result["scan_warnings"],
                "hash_skipped": result["hash_skipped"],
            }

            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.RESULT,
                payload=summary,
                in_reply_to=message.message_id,
            )

        except (ValueError, PermissionError, OSError) as error:
            return AgentMessage(
                task_id=message.task_id,
                sender=self.name,
                recipient=message.sender,
                message_type=MessageType.ERROR,
                payload={"error": str(error)},
                in_reply_to=message.message_id,
            )