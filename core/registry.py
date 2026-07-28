from core.tool import Tool


class ToolRegistry:

    def __init__(self):
        self.tools = {}

    def register(self, tool):
        if not isinstance(tool, Tool):
            raise TypeError(
                "Only objects that inherit from Tool can be registered."
            )

        if not tool.name:
            raise ValueError(
                f"{tool.__class__.__name__} has no tool name."
            )

        if tool.name in self.tools:
            raise ValueError(
                f"A tool named '{tool.name}' is already registered."
            )

        self.tools[tool.name] = tool

    def get(self, tool_name):
        return self.tools.get(tool_name)

    def execute(self, tool_name, args=None):
        tool = self.get(tool_name)

        if tool is None:
            return f"Tool '{tool_name}' was not found."

        try:
            return tool.execute(args)

        except Exception as error:
            return f"Tool '{tool_name}' failed: {error}"

    def list_tools(self):
        return sorted(self.tools.keys())