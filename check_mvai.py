from __future__ import annotations

import compileall
import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent

    print("[1/4] Compiling MV.ai source files...")
    ok = compileall.compile_dir(
        root,
        quiet=1,
        rx=re.compile(r"[\\/](?:\.venv|build|dist|__pycache__)[\\/]"),
    )
    if not ok:
        print("[FAILED] One or more Python files have syntax errors.")
        return 1

    print("[2/4] Importing the UI package...")
    import ui
    from ui.window import MVWindow

    print("[3/4] Checking email planning support...")
    from ai.planner import TaskPlanner
    from core.permissions import PermissionManager

    assert "email" in TaskPlanner.LAPTOP_TOOLS
    assert "send_email" in TaskPlanner.TOOL_ACTIONS["email"]
    assert TaskPlanner.REQUIRED_ARGUMENTS[("email", "send_email")] == {
        "to",
        "subject",
        "body",
    }
    assert PermissionManager().requires_confirmation("email", "send_email")

    print("[4/4] Checking core imports...")
    from core.assistant import Assistant

    assert ui is not None
    assert MVWindow is not None
    assert Assistant is not None

    print("[PASSED] MV.ai source, imports, email schema, and permissions are ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
