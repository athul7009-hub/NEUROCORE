
import json

from app.agents.coordinator import Coordinator
from app.runtime import create_runtime
from app.core.config import settings
from app.core.schemas import TaskIntent, TaskRequest
from app.core.schemas import ToolRequest, ToolStatus
from app.core.schemas import TaskIntent, TaskRequest, ToolRequest, ToolStatus
import logging
logger = logging.getLogger(__name__)
def display_response(response):
    print(f"\nStatus: {response.message_type.value}")
    print(f"Agent: {response.sender}")
    print("\nResponse:")
    print(json.dumps(
        response.payload,
        indent=2,
        ensure_ascii=False,
        default=str,
    ))

    if response.metadata:
        print("\nMetadata:")
        print(json.dumps(
            response.metadata,
            indent=2,
            ensure_ascii=False,
            default=str,
        ))



def run_cli(coordinator: Coordinator):
    while True:
        print("\n========== NEUROCORE ==========")
        print("1. File Analysis")
        print("2. Create Plan")
        print("3. Scan Directory")
        print("0. Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "0":
            print("NEUROCORE stopped.")
            break

        if choice == "3":
            run_directory_scan(coordinator)
            continue

        if choice == "1":
            if not settings.allowed_scan_roots:
                print("No approved scan directories configured.")
                continue

            print("\nApproved directories:")
            for root in settings.allowed_scan_roots:
                print(f"- {root}")

            directory = input("\nDirectory to analyze: ").strip()

            if not directory:
                print("Directory cannot be empty.")
                continue

            task = TaskRequest(
                user_input="Analyze the selected directory.",
                intent=TaskIntent.FILE_ANALYSIS,
                parameters={"directory": directory},
            )

        elif choice == "2":
            objective = input("\nDescribe your task: ").strip()

            if not objective:
                print("Task description cannot be empty.")
                continue

            task = TaskRequest(
                user_input=objective,
                intent=TaskIntent.PLAN_TASK,
            )

        else:
            print("Invalid option.")
            continue

        response = coordinator.handle_task(task)
        display_response(response)

def main():
    try:
        runtime = create_runtime()
        print("NEUROCORE initialized successfully.")
        run_cli(runtime.coordinator)

    except KeyboardInterrupt:
        print("\nNEUROCORE stopped.")

    except Exception:
        print("NEUROCORE could not start due to an internal error.")
        raise

def run_directory_scan(coordinator):
    directory = input("Enter directory path to scan: ").strip()

    if not directory:
        print("Directory path cannot be empty.")
        return

    request = ToolRequest(
        tool_name="scan_directory",
        parameters={"directory": directory},
        requires_approval=False,
        dry_run=False,
        
    )

    try:
        result = coordinator.execute_tool(request)

        if result.status == ToolStatus.PROPOSED:
            print(f"\nApproval required: {result.message}")

            decision = input("Approve execution? (y/n): ").strip().lower()

            if decision == "y":
                coordinator.approve_tool(request.action_id)
                result = coordinator.execute_tool(request)

            elif decision == "n":
                coordinator.reject_tool(request.action_id)
                print("Tool execution rejected.")
                return

            else:
                coordinator.reject_tool(request.action_id)
                print("Invalid decision. Tool execution was not approved.")
                return

        if not result.success:
            print(f"Tool execution failed: {result.message}")
            return

        data = result.data

        print("\n--- Directory Scan Results ---")
        print(f"Root: {data.get('root')}")
        print(f"Total files: {data.get('total_files')}")
        print(f"Total size: {data.get('total_size_bytes')} bytes")
        print(f"Recoverable bytes: {data.get('recoverable_bytes')}")

        print("\nExtension counts:")
        for extension, count in data.get("extension_counts", {}).items():
            print(f"  {extension}: {count}")

        print(f"\nDuplicate groups: {len(data.get('duplicates', []))}")
        print(f"Scan warnings: {len(data.get('scan_warnings', []))}")
        print(f"Hash-skipped files: {len(data.get('hash_skipped', []))}")

    except Exception:
        logger.exception("Directory scan operation failed.")
        print("Tool operation failed. Check the application logs.")
