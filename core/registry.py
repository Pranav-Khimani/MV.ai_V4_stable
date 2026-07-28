from __future__ import annotations

from core.tool import Tool
from core.tool_schema import ActionSchema, ToolSchema


class ToolRegistry:
    """Stores tools and exposes their schemas to every MV.ai subsystem."""

    def __init__(self):
        self.tools: dict[str, Tool] = {}
        self.schemas: dict[str, ToolSchema] = {}

    def register(self, tool: Tool) -> None:
        if not isinstance(tool, Tool):
            raise TypeError(
                "Only objects that inherit from Tool can be registered."
            )

        schema = tool.get_schema()

        if schema.name in self.tools:
            raise ValueError(
                f"A tool named '{schema.name}' is already registered."
            )

        self.tools[schema.name] = tool
        self.schemas[schema.name] = schema

    def get(self, tool_name: str):
        return self.tools.get(str(tool_name).strip().lower())

    def get_schema(self, tool_name: str) -> ToolSchema | None:
        return self.schemas.get(str(tool_name).strip().lower())

    def get_action_schema(
        self,
        tool_name: str,
        action: str,
    ) -> ActionSchema | None:
        schema = self.get_schema(tool_name)
        if schema is None:
            return None
        return schema.actions.get(str(action).strip().lower())

    def execute(self, tool_name: str, args=None):
        tool = self.get(tool_name)

        if tool is None:
            return f"Tool '{tool_name}' was not found."

        try:
            return tool.execute(args)
        except Exception as error:
            return f"Tool '{tool_name}' failed: {error}"

    def list_tools(self) -> list[str]:
        return sorted(self.tools)

    def list_schemas(self) -> list[ToolSchema]:
        return [
            self.schemas[name]
            for name in sorted(self.schemas)
        ]

    def supported_devices(self) -> set[str]:
        return {
            device
            for schema in self.schemas.values()
            for device in schema.devices
        }

    def tools_for_device(self, device: str) -> set[str]:
        normalized_device = str(device).strip().lower()
        return {
            schema.name
            for schema in self.schemas.values()
            if normalized_device in schema.devices
        }

    def supports_device(self, tool_name: str, device: str) -> bool:
        schema = self.get_schema(tool_name)
        if schema is None:
            return False
        return str(device).strip().lower() in schema.devices

    def supports_action(self, tool_name: str, action: str) -> bool:
        return self.get_action_schema(tool_name, action) is not None
