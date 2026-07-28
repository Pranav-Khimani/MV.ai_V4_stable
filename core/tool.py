from abc import ABC, abstractmethod


class Tool(ABC):
    """
    Base class for every MV.AI tool.
    """

    name = ""
    description = ""

    @abstractmethod
    def execute(self, args=None):
        """
        Execute the tool.
        """
        pass