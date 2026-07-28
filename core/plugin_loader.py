import importlib
import inspect
import pkgutil

import tools
from core.tool import Tool


def discover_tools():
    """
    Search every Python module inside the tools package
    and automatically create all Tool subclasses.
    """

    discovered_tools = []
    loading_errors = []

    package_prefix = f"{tools.__name__}."

    for module_info in pkgutil.walk_packages(
        tools.__path__,
        prefix=package_prefix,
    ):
        # Skip folders themselves.
        if module_info.ispkg:
            continue

        module_name = module_info.name

        try:
            module = importlib.import_module(module_name)

        except Exception as error:
            loading_errors.append(
                f"Could not load {module_name}: {error}"
            )
            continue

        for _, tool_class in inspect.getmembers(
            module,
            inspect.isclass,
        ):
            # Ignore the base Tool class and unrelated classes.
            if tool_class is Tool:
                continue

            if not issubclass(tool_class, Tool):
                continue

            # Ignore classes imported from another module.
            if tool_class.__module__ != module.__name__:
                continue

            # Ignore unfinished abstract classes.
            if inspect.isabstract(tool_class):
                continue

            try:
                tool_instance = tool_class()
                discovered_tools.append(tool_instance)

            except Exception as error:
                loading_errors.append(
                    f"Could not create {tool_class.__name__}: {error}"
                )

    return discovered_tools, loading_errors