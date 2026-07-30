from __future__ import annotations

from core.registry import ToolRegistry
from core.tool_schema import PERMISSION_CONFIRM


class PermissionManager:
    """Reads confirmation policy directly from registered tool schemas."""

    def __init__(self, registry: ToolRegistry | None = None):
        self.registry = registry or self._discover_registry()

    @staticmethod
    def _discover_registry() -> ToolRegistry:
        """Build a schema registry for standalone permission tests."""

        from core.plugin_loader import discover_tools

        registry = ToolRegistry()
        tools, errors = discover_tools()

        for tool in tools:
            registry.register(tool)

        if errors:
            raise RuntimeError(
                "Could not load tool schemas: " + "; ".join(errors)
            )

        return registry

    def requires_confirmation(
        self,
        tool_name: str,
        action: str,
    ) -> bool:
        action_schema = self.registry.get_action_schema(
            tool_name,
            action,
        )
        return bool(
            action_schema
            and action_schema.permission == PERMISSION_CONFIRM
        )

    def get_confirmation_message(
        self,
        tool_name: str,
        action: str,
        args: dict | None = None,
    ) -> str:
        action_schema = self.registry.get_action_schema(
            tool_name,
            action,
        )

        if action_schema and action_schema.confirmation_message:
            template = action_schema.confirmation_message
            try:
                return template.format_map(_SafeFormatDict(args or {}))
            except (KeyError, ValueError):
                return template

        return f"Allow '{action}'?"

    def apply_policy(self, parsed: dict) -> dict:
        """Keep compatibility with the older rule-based parser."""

        tool_name = parsed.get("tool")
        args = parsed.get("args") or {}
        action = args.get("action")

        if self.requires_confirmation(tool_name, action):
            parsed["requires_confirmation"] = True
            parsed["confirmation_message"] = (
                self.get_confirmation_message(tool_name, action, args)
            )

        return parsed

    def confirm(self, message: str) -> bool:
        """Temporary terminal confirmation for non-GUI use."""

        print()
        print("MV.AI:", message)

        answer = input("(yes/no): ").strip().lower()
        return answer in {"yes", "y"}


class _SafeFormatDict(dict):
    """Leave unknown confirmation placeholders visible instead of failing."""

    def __missing__(self, key):
        return "{" + str(key) + "}"
