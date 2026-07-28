from abc import ABC, abstractmethod

from core.tool_schema import ActionSchema, ToolSchema


class Tool(ABC):
    """Base class for every MV.ai tool."""

    name = ""
    description = ""
    supported_devices = ("laptop",)
    actions: dict[str, ActionSchema] = {}
    prompt_rules: tuple[str, ...] = ()

    def get_schema(self) -> ToolSchema:
        """Return and validate this tool's declarative schema."""

        return ToolSchema(
            name=self.name,
            description=self.description,
            devices=tuple(self.supported_devices),
            actions=dict(self.actions),
            prompt_rules=tuple(self.prompt_rules),
        )

    @abstractmethod
    def execute(self, args=None):
        """Execute the tool."""

        raise NotImplementedError
