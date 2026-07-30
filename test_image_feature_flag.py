from __future__ import annotations

import os

os.environ["MV_IMAGE_GENERATION_ENABLED"] = "false"

from ai.planner import TaskPlanner
from core.feature_flags import image_generation_enabled
from core.plugin_loader import discover_tools
from core.registry import ToolRegistry


def main() -> int:
    assert image_generation_enabled() is False
    assert TaskPlanner.is_image_generation_request(
        "Generate an image of a cute cat."
    )
    assert not TaskPlanner.is_image_generation_request(
        "Analyze this attached image."
    )

    tools, errors = discover_tools()
    assert not errors, errors

    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)

    assert registry.get("images") is None
    assert registry.get("email") is not None
    assert registry.get("files") is not None

    print("[PASSED] Image generation is disabled.")
    print("[PASSED] Image-generation tool is not registered.")
    print("[PASSED] Image analysis code remains separate and available.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
