from abc import ABC, abstractmethod

from ai.models import TaskPlan


class AIProvider(ABC):
    """
    Base class for every AI provider used by MV.AI.
    """

    @abstractmethod
    def generate_plan(self, command: str) -> TaskPlan:
        """
        Convert a natural-language request into a multi-step TaskPlan.
        """
        raise NotImplementedError