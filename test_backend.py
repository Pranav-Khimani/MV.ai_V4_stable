from ai.models import TaskPlan, TaskStep
from ai.planner import TaskPlanner
from ai.provider import AIProvider

from core.executor import TaskExecutor
from core.permissions import PermissionManager
from core.plugin_loader import discover_tools
from core.registry import ToolRegistry


class TestProvider(AIProvider):
    """
    A temporary fake AI provider.

    It lets us test the complete backend without using Gemini
    or consuming API requests.
    """

    def generate_plan(self, command: str) -> TaskPlan:
        return TaskPlan(
            goal="Check the computer time",
            steps=[
                TaskStep(
                    device="laptop",
                    tool="system",
                    args={
                        "action": "time",
                    },
                    description="Get the current computer time.",
                )
            ],
            message="",
        )


def print_separator():
    print("\n" + "=" * 60 + "\n")


def main():
    print_separator()
    print("MV.AI BACKEND TEST")
    print_separator()

    # --------------------------------------------------
    # 1. Discover plugins
    # --------------------------------------------------

    print("1. Discovering tool plugins...")

    discovered_tools, loading_errors = discover_tools()

    print(f"Discovered tool objects: {len(discovered_tools)}")

    if loading_errors:
        print("\nPlugin loading errors:")

        for error in loading_errors:
            print(f"  - {error}")
    else:
        print("No plugin loading errors.")

    # --------------------------------------------------
    # 2. Register plugins
    # --------------------------------------------------

    print_separator()
    print("2. Registering tools...")

    registry = ToolRegistry()
    registration_errors = []

    for tool in discovered_tools:
        try:
            registry.register(tool)
            print(f"  Registered: {tool.name}")

        except Exception as error:
            registration_errors.append(str(error))
            print(f"  Registration failed: {error}")

    registered_tools = registry.list_tools()

    print("\nRegistered tools:")
    print(registered_tools)

    if not registered_tools:
        print("\nTEST FAILED: No tools were registered.")
        return

    # --------------------------------------------------
    # 3. Create and validate a plan
    # --------------------------------------------------

    print_separator()
    print("3. Creating a test task plan...")

    provider = TestProvider()
    planner = TaskPlanner(provider, registry)

    plan = planner.create_plan(
        "What time is it?"
    )

    print("Goal:", plan.goal)
    print("Message:", plan.message)
    print("Steps:", len(plan.steps))

    for index, step in enumerate(plan.steps, start=1):
        print(f"\nStep {index}:")
        print("  Device:", step.device)
        print("  Tool:", step.tool)
        print("  Arguments:", step.args)
        print("  Description:", step.description)

    if not plan.steps:
        print("\nTEST FAILED: Planner returned no steps.")
        return

    # --------------------------------------------------
    # 4. Execute the plan
    # --------------------------------------------------

    print_separator()
    print("4. Executing the task plan...")

    permission_manager = PermissionManager(registry)

    executor = TaskExecutor(
        registry=registry,
        permission_manager=permission_manager,
    )

    def progress_callback(
        step_number,
        total_steps,
        step,
    ):
        print(
            f"Executing step "
            f"{step_number}/{total_steps}: "
            f"{step.description}"
        )

    def confirmation_callback(
        message,
        step,
    ):
        print(f"Confirmation requested: {message}")

        # The current time test should never require confirmation.
        return False

    report = executor.execute_plan(
        plan=plan,
        confirmation_callback=confirmation_callback,
        progress_callback=progress_callback,
    )

    # --------------------------------------------------
    # 5. Display report
    # --------------------------------------------------

    print_separator()
    print("5. Execution report")

    print("Goal:", report.goal)
    print("Success:", report.success)
    print(
        "Completed steps:",
        f"{report.completed_steps}/{report.total_steps}",
    )
    print("Message:", report.message)

    for result in report.results:
        print(f"\nStep {result.step_number}:")
        print("  Tool:", result.tool)
        print("  Action:", result.action)
        print("  Success:", result.success)
        print("  Output:", result.output)
        print("  Error:", result.error)

    print_separator()

    if report.success:
        print("BACKEND TEST PASSED ✅")
    else:
        print("BACKEND TEST FAILED ❌")

    print_separator()


if __name__ == "__main__":
    main()