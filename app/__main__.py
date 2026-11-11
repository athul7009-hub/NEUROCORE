
import json

from app.agents.coordinator import Coordinator
from app.bootstrap import create_coordinator
from app.core.config import settings
from app.core.schemas import TaskIntent, TaskRequest


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
        print("0. Exit")

        choice = input("\nSelect an option: ").strip()

        if choice == "0":
            print("NEUROCORE stopped.")
            break

        if choice == "1":
            if not settings.allowed_scan_roots:
                print("No approved scan directories configured.")
                continue

            print("\nApproved directories:")
            for root in settings.allowed_scan_roots:
                print(f"- {root}")

            directory = input("\nDirectory to analyze: ").strip()

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
        coordinator = create_coordinator()
        print("NEUROCORE initialized successfully.")
        run_cli(coordinator)

    except KeyboardInterrupt:
        print("\nNEUROCORE stopped.")

    except Exception:
        print("NEUROCORE could not start due to an internal error.")
        raise


if __name__ == "__main__":
    main()
