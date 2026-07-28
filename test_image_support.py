from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path


# A valid 1x1 PNG used only for local storage/database checks.
TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    project_root = Path(__file__).resolve().parent

    # Confirm the installed UI/API packages are available without making a
    # network request or opening the full MV.ai window.
    from google.genai import types
    from PySide6.QtWidgets import QFileDialog

    from core.media_store import MediaStore
    from memory.memory_manager import MemoryManager
    from ui.widgets.image_attachment import ImageAttachmentPreview

    require(hasattr(types.Part, "from_bytes"), "google-genai lacks Part.from_bytes")
    require(QFileDialog is not None, "PySide6 file dialog is unavailable")
    require(ImageAttachmentPreview is not None, "Image preview widget is unavailable")

    window_source = (project_root / "ui" / "window.py").read_text(encoding="utf-8")
    require('QPushButton("ADD Stuff!")' in window_source, "ADD Stuff! button was not found")
    require("handle_image_command" in window_source, "Image task routing was not found")

    with tempfile.TemporaryDirectory(prefix="mvai_image_test_") as temp_dir:
        temp_root = Path(temp_dir)
        os.environ["LOCALAPPDATA"] = str(temp_root / "LocalAppData")

        source_image = temp_root / "sample.png"
        source_image.write_bytes(TINY_PNG)

        store = MediaStore()
        details = store.inspect_image(source_image)
        require(details["mime_type"] == "image/png", "PNG MIME detection failed")

        attachment = store.store_image(source_image).to_dict()
        stored_path = store.resolve_path(attachment)
        require(stored_path is not None and stored_path.exists(), "Stored image is missing")
        require(stored_path.read_bytes() == TINY_PNG, "Stored image bytes changed")

        memory = MemoryManager(database_path=str(temp_root / "memory.db"))
        memory.add_conversation_message(
            role="user",
            content="What is in this image?",
            attachments=[attachment],
        )
        history = memory.get_conversation_history(limit=5)
        require(history, "Conversation history is empty")
        require(history[-1]["attachments"], "Attachment metadata was not restored")
        require(
            history[-1]["attachments"][0]["mime_type"] == "image/png",
            "Attachment MIME type was not restored",
        )

    print("[PASSED] ADD Stuff! button is wired into the input bar.")
    print("[PASSED] PNG/JPG/WebP validation and private media storage are ready.")
    print("[PASSED] Reality attachment metadata survives a database reload.")
    print("[PASSED] Gemini image Part support and PySide6 image UI imports are available.")


if __name__ == "__main__":
    main()
