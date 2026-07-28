from dataclasses import dataclass, field
from typing import Any


@dataclass
class TaskStep:
    """
    Represents one step in a larger MV.AI task.
    """

    device: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def to_dict(self) -> dict:
        return {
            "device": self.device,
            "tool": self.tool,
            "args": self.args,
            "description": self.description,
        }


@dataclass
class TaskPlan:
    """
    Represents the complete plan for a user's task.
    """

    goal: str
    steps: list[TaskStep] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "steps": [
                step.to_dict()
                for step in self.steps
            ],
            "message": self.message,
        }

    @classmethod
    def empty(cls, message: str) -> "TaskPlan":
        return cls(
            goal="",
            steps=[],
            message=message,
        )