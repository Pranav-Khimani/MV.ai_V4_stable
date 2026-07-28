from dataclasses import dataclass, field
from typing import Any, Callable

from ai.models import TaskPlan, TaskStep
from core.permissions import PermissionManager
from core.task_manager import CancellationToken, TaskCancelledError
from core.registry import ToolRegistry


@dataclass
class StepResult:
    """
    Result of one executed task step.
    """

    step_number: int
    description: str
    tool: str
    action: str
    success: bool
    output: Any = None
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "step_number": self.step_number,
            "description": self.description,
            "tool": self.tool,
            "action": self.action,
            "success": self.success,
            "output": self.output,
            "error": self.error,
        }


@dataclass
class ExecutionReport:
    """
    Complete result of executing a TaskPlan.
    """

    goal: str
    success: bool
    completed_steps: int
    total_steps: int
    results: list[StepResult] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "success": self.success,
            "completed_steps": self.completed_steps,
            "total_steps": self.total_steps,
            "results": [
                result.to_dict()
                for result in self.results
            ],
            "message": self.message,
        }


class TaskExecutor:
    """
    Executes validated TaskPlan steps using registered tools.

    MVP behavior:
    - Runs steps one by one.
    - Stops when a step fails.
    - Requests confirmation for sensitive actions.
    - Returns a full ExecutionReport.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        permission_manager: PermissionManager | None = None,
    ):
        self.registry = registry
        self.permission_manager = (
            permission_manager or PermissionManager()
        )

    def execute_plan(
        self,
        plan: TaskPlan,
        confirmation_callback: Callable | None = None,
        progress_callback: Callable | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> ExecutionReport:
        """
        Execute every step in a TaskPlan.

        confirmation_callback should look like:

            callback(message, step) -> bool

        progress_callback should look like:

            callback(step_number, total_steps, step)
        """

        if not isinstance(plan, TaskPlan):
            return ExecutionReport(
                goal="",
                success=False,
                completed_steps=0,
                total_steps=0,
                message="The executor received an invalid task plan.",
            )

        if not plan.steps:
            return ExecutionReport(
                goal=plan.goal,
                success=False,
                completed_steps=0,
                total_steps=0,
                message=(
                    plan.message
                    or "The task plan contains no executable steps."
                ),
            )

        results: list[StepResult] = []
        total_steps = len(plan.steps)
        completed_steps = 0

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        for step_number, step in enumerate(
            plan.steps,
            start=1,
        ):
            if cancellation_token is not None:
                cancellation_token.raise_if_cancelled()
            if callable(progress_callback):
                try:
                    progress_callback(
                        step_number,
                        total_steps,
                        step,
                    )
                except Exception:
                    pass

            result = self.execute_step(
                step=step,
                step_number=step_number,
                confirmation_callback=confirmation_callback,
                cancellation_token=cancellation_token,
            )

            results.append(result)

            if not result.success:
                return ExecutionReport(
                    goal=plan.goal,
                    success=False,
                    completed_steps=completed_steps,
                    total_steps=total_steps,
                    results=results,
                    message=(
                        f"Task stopped at step {step_number}: "
                        f"{result.error}"
                    ),
                )

            completed_steps += 1

        return ExecutionReport(
            goal=plan.goal,
            success=True,
            completed_steps=completed_steps,
            total_steps=total_steps,
            results=results,
            message=(
                plan.message
                or "Task completed successfully."
            ),
        )

    def execute_step(
        self,
        step: TaskStep,
        step_number: int,
        confirmation_callback: Callable | None = None,
        cancellation_token: CancellationToken | None = None,
    ) -> StepResult:
        """
        Execute one task step.
        """

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        if not isinstance(step, TaskStep):
            return StepResult(
                step_number=step_number,
                description="",
                tool="",
                action="",
                success=False,
                error="The step is invalid.",
            )

        action = self.get_action(step)

        if step.device != "laptop":
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action=action,
                success=False,
                error=(
                    f"Device '{step.device}' is not connected "
                    f"or implemented yet."
                ),
            )

        if not action:
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action="",
                success=False,
                error="The step has no action.",
            )

        permission_error = self.check_permission(
            step=step,
            action=action,
            confirmation_callback=confirmation_callback,
        )

        if permission_error:
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action=action,
                success=False,
                error=permission_error,
            )

        tool = self.registry.get(step.tool)

        if tool is None:
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action=action,
                success=False,
                error=f"Tool '{step.tool}' was not found.",
            )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        try:
            output = tool.execute(dict(step.args))

        except Exception as error:
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action=action,
                success=False,
                error=str(error),
            )

        if cancellation_token is not None:
            cancellation_token.raise_if_cancelled()

        if self.output_indicates_failure(output):
            return StepResult(
                step_number=step_number,
                description=step.description,
                tool=step.tool,
                action=action,
                success=False,
                output=output,
                error=str(output),
            )

        return StepResult(
            step_number=step_number,
            description=step.description,
            tool=step.tool,
            action=action,
            success=True,
            output=output,
        )

    def check_permission(
        self,
        step: TaskStep,
        action: str,
        confirmation_callback: Callable | None = None,
    ) -> str | None:
        """
        Ask for confirmation when the action is sensitive.
        """

        requires_confirmation = (
            self.permission_manager.requires_confirmation(
                step.tool,
                action,
            )
        )

        if not requires_confirmation:
            return None

        confirmation_message = (
            self.permission_manager.get_confirmation_message(
                step.tool,
                action,
            )
        )

        if not callable(confirmation_callback):
            return (
                f"Action '{action}' requires confirmation, "
                f"but no confirmation interface is available."
            )

        try:
            confirmed = confirmation_callback(
                confirmation_message,
                step,
            )

        except Exception as error:
            return (
                f"Could not request confirmation: {error}"
            )

        if not confirmed:
            return (
                f"The user cancelled action '{action}'."
            )

        return None

    @staticmethod
    def get_action(step: TaskStep) -> str:
        """
        Read and normalize the action name from step arguments.
        """

        action = step.args.get("action", "")

        if not isinstance(action, str):
            return ""

        return action.strip().lower()

    @staticmethod
    def output_indicates_failure(output: Any) -> bool:
        """
        Detect failures returned by existing string-based tools.

        Later, tools can return structured ToolResult objects.
        """

        if output is None:
            return False

        if not isinstance(output, str):
            return False

        normalized = output.strip().lower()

        failure_phrases = (
            "failed:",
            "error:",
            "was not found",
            "could not",
            "unable to",
            "not supported",
            "does not exist",
        )

        return any(
            phrase in normalized
            for phrase in failure_phrases
        )