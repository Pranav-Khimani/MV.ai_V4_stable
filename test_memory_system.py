from __future__ import annotations

import json
import tempfile
from pathlib import Path

from memory.memory_commands import MemoryCommandRouter
from memory.memory_manager import MemoryManager
from memory.memory_policy import SensitiveMemoryError
from memory.user_profile import UserProfile
from tools.memory.memory_tools import MemoryTool


def execute_single(tool: MemoryTool, plan):
    assert len(plan.steps) == 1
    return tool.execute(plan.steps[0].args)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mvai_memory_test_") as temp_dir:
        root = Path(temp_dir)
        profile_path = root / "user_profile.json"
        profile_path.write_text(
            json.dumps(
                {
                    "personal": {
                        "name": "Pranav",
                        "nickname": "Multiverse",
                    },
                    "projects": {"main_project": "MV.ai"},
                }
            ),
            encoding="utf-8",
        )

        manager = MemoryManager(str(root / "memory.db"))
        profile = UserProfile(profile_path)
        router = MemoryCommandRouter(manager, profile)
        tool = MemoryTool(manager)

        remember_plan = router.create_plan(
            "Remember that my college documents are in Documents."
        )
        assert remember_plan is not None
        assert remember_plan.steps[0].args["action"] == "remember_memory"
        remembered = execute_single(tool, remember_plan)
        assert "Remembered:" in remembered

        stored = manager.search_relevant("college folder", limit=5)
        assert stored
        assert stored[0]["category"] == "folder"
        assert stored[0]["memory_value"] == "Documents"

        duplicate_plan = router.create_plan(
            "Remember that my college documents are in Documents."
        )
        assert duplicate_plan is not None
        assert not duplicate_plan.steps
        assert "already remember" in duplicate_plan.message.lower()

        recall_plan = router.create_plan(
            "What do you remember about college files?"
        )
        assert recall_plan is not None
        recalled = execute_single(tool, recall_plan)
        assert "college documents" in recalled.lower()

        update_plan = router.create_plan(
            "Update my college documents to D:/College."
        )
        assert update_plan is not None
        assert update_plan.steps[0].args["action"] == "update_memory"
        updated = execute_single(tool, update_plan)
        assert "Updated:" in updated
        assert manager.search_relevant("college documents")[0]["memory_value"] == "D:/College"

        all_plan = router.create_plan("What do you remember about me?")
        assert all_plan is not None
        assert not all_plan.steps
        assert "Pranav" in all_plan.message
        assert "D:/College" in all_plan.message

        forget_plan = router.create_plan("Forget my college documents.")
        assert forget_plan is not None
        assert forget_plan.steps[0].args["action"] == "forget_memory"
        forgotten = execute_single(tool, forget_plan)
        assert "Forgotten:" in forgotten
        assert not manager.get_all_memories()

        try:
            tool.execute(
                {
                    "action": "remember_memory",
                    "key": "gemini_api_key",
                    "value": "AIzaThisMustNeverBeStored123456789",
                }
            )
        except SensitiveMemoryError:
            pass
        else:
            raise AssertionError("Sensitive credentials must be rejected.")

        manager.end_session()

    print("[PASSED] Local remember, recall, update, and forget commands work.")
    print("[PASSED] Profile and SQLite memories remain separate but can be summarized.")
    print("[PASSED] Duplicate detection, fuzzy search, and secret blocking work.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
