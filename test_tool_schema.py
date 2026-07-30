from __future__ import annotations

from ai.models import TaskPlan, TaskStep
from ai.planner import TaskPlanner
from ai.prompts import build_system_prompt
from ai.provider import AIProvider
from core.feature_flags import image_generation_enabled
from core.permissions import PermissionManager
from core.plugin_loader import discover_tools
from core.registry import ToolRegistry
from core.tool_schema import PERMISSION_CONFIRM


class NoCallProvider(AIProvider):
    """Provider that must never be called by schema validation tests."""

    def generate_plan(self, command: str) -> TaskPlan:
        raise AssertionError("Gemini should not be called by this test.")


def build_registry() -> ToolRegistry:
    tools, loading_errors = discover_tools()
    assert not loading_errors, loading_errors

    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


def main() -> int:
    registry = build_registry()
    planner = TaskPlanner(NoCallProvider(), registry)
    permissions = PermissionManager(registry)

    expected_tools = {
        "apps",
        "browser",
        "device",
        "email",
        "files",
        "memory",
        "system",
        "workflow",
    }
    if image_generation_enabled():
        expected_tools.add("images")
    assert set(registry.list_tools()) == expected_tools

    checked_actions = 0

    for tool_schema in registry.list_schemas():
        assert registry.get(tool_schema.name) is not None
        assert tool_schema.description
        assert tool_schema.devices
        assert tool_schema.actions

        for action_name, action_schema in tool_schema.actions.items():
            args = {
                "action": action_name,
                **dict(action_schema.example),
            }
            step = TaskStep(
                device=tool_schema.devices[0],
                tool=tool_schema.name,
                args=args,
                description="Schema validation test.",
            )
            error = planner.validate_step(step, checked_actions + 1)
            assert error is None, (
                f"{tool_schema.name}.{action_name} failed validation: {error}"
            )

            needs_confirmation = (
                action_schema.permission == PERMISSION_CONFIRM
            )
            assert permissions.requires_confirmation(
                tool_schema.name,
                action_name,
            ) is needs_confirmation

            if needs_confirmation:
                assert permissions.get_confirmation_message(
                    tool_schema.name,
                    action_name,
                ) == action_schema.confirmation_message

            if action_schema.required_arguments:
                missing_name = action_schema.required_arguments[0]
                incomplete_args = dict(args)
                incomplete_args.pop(missing_name)
                incomplete_step = TaskStep(
                    device=tool_schema.devices[0],
                    tool=tool_schema.name,
                    args=incomplete_args,
                )
                missing_error = planner.validate_step(
                    incomplete_step,
                    1,
                )
                assert missing_error is not None
                assert missing_name in missing_error

            checked_actions += 1

    prompt = build_system_prompt(registry.list_schemas())
    for tool_schema in registry.list_schemas():
        assert f"TOOL: {tool_schema.name}" in prompt
        for action_name in tool_schema.actions:
            assert f"ACTION: {action_name}" in prompt

    assert not hasattr(TaskPlanner, "TOOL_ACTIONS")
    assert not hasattr(TaskPlanner, "REQUIRED_ARGUMENTS")
    assert not hasattr(TaskPlanner, "LAPTOP_TOOLS")
    assert not hasattr(PermissionManager, "SENSITIVE_ACTIONS")

    email_plan = planner.try_create_direct_email_plan(
        "Send an email to test@example.com saying hello, "
        "with subject Schema test."
    )
    assert email_plan is not None
    assert planner.validate_plan(email_plan).steps


    image_plan = planner.try_create_direct_image_plan(
        "Generate an image of a futuristic purple city at night in 16:9."
    )
    assert image_plan is not None
    validated_image_plan = planner.validate_plan(image_plan)

    if image_generation_enabled():
        assert validated_image_plan.steps
        assert validated_image_plan.steps[0].tool == "images"
        assert validated_image_plan.steps[0].args["action"] == "generate_image"
        assert validated_image_plan.steps[0].args["aspect_ratio"] == "16:9"
    else:
        assert not validated_image_plan.steps

    print(f"[PASSED] {len(expected_tools)} tools registered.")
    print(f"[PASSED] {checked_actions} actions validated from one schema system.")
    print("[PASSED] Planner, prompt, and permissions use the same schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
