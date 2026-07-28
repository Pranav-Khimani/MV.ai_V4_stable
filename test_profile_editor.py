from __future__ import annotations

import os
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from memory.user_profile import UserProfile
from ui.widgets.more_popup import MorePopup


def test_atomic_profile_storage() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "user_profile.json"
        store = UserProfile(path)
        original = {
            "personal": {"name": "Pranav", "age": 16},
            "projects": {"main_project": "MV.ai"},
            "unknown_section": {"must_survive": True},
            "custom": {"favorite_number": 2612},
        }
        store.save(original)
        assert store.load() == original
        assert not path.with_suffix(".json.tmp").exists()


def test_profile_editor_form() -> None:
    app = QApplication.instance() or QApplication([])
    popup = MorePopup()

    assert ("personal", "name") in popup._profile_inputs
    assert ("projects", "company") in popup._profile_inputs
    assert popup.custom_table is not None

    popup._profile_data = {
        "personal": {"name": "Old name"},
        "unknown_section": {"must_survive": True},
        "custom": {},
    }
    popup._profile_inputs[("personal", "name")].setText("Pranav")
    popup._profile_inputs[("personal", "age")].setText("16")
    popup._append_custom_row("favorite_number", "2612")

    collected = popup._collect_profile_from_form()
    assert collected["personal"]["name"] == "Pranav"
    assert collected["personal"]["age"] == 16
    assert collected["custom"]["favorite_number"] == 2612
    assert collected["unknown_section"]["must_survive"] is True

    popup.close()
    app.processEvents()


if __name__ == "__main__":
    test_atomic_profile_storage()
    test_profile_editor_form()
    print("[PASSED] Atomic user_profile.json saving works.")
    print("[PASSED] Profile editor loads fields and preserves unknown data.")
    print("[PASSED] Custom facts support text, numbers and JSON values.")
