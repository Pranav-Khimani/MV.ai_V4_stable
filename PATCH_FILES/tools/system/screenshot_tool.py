from __future__ import annotations

from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication

from core.tool import Tool
from core.tool_schema import ActionSchema


class ScreenshotTool(Tool):
    """Capture the desktop without opening the saved image."""

    name = "screenshot"
    description = "Capture the desktop and save it as a PNG image."
    actions = {
        "capture": ActionSchema(
            description="Capture the current desktop and save it as a PNG.",
            example={},
        ),
        "open_folder": ActionSchema(
            description="Open the folder containing MV.AI screenshots.",
            example={},
        ),
    }
    prompt_rules = (
        "Use screenshot.capture when the user asks to take or capture a screenshot.",
        "Use screenshot.open_folder only when the user asks to open the screenshots folder.",
    )

    def __init__(self) -> None:
        self.screenshot_folder = Path.home() / "Pictures" / "MV.AI Screenshots"
        self.screenshot_folder.mkdir(parents=True, exist_ok=True)

    def execute(self, args=None):
        args = args or {}
        action = str(args.get("action", "capture")).strip().lower()

        if action in {"open_folder", "folder", "show_folder"}:
            return self.open_folder()

        if action in {"capture", "take", "screenshot"}:
            return self.capture()

        return "Unknown screenshot action."

    def capture(self) -> str:
        app = QApplication.instance()
        if app is None:
            raise RuntimeError("The desktop application is not running.")

        screen = app.primaryScreen()
        if screen is None:
            raise RuntimeError("No display was detected.")

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        screenshot_path = self.screenshot_folder / f"MVAI_Screenshot_{timestamp}.png"

        pixmap = screen.grabWindow(0)
        if pixmap.isNull():
            raise RuntimeError("Windows did not provide a screenshot image.")

        if not pixmap.save(str(screenshot_path), "PNG"):
            raise RuntimeError("The screenshot could not be saved.")

        # Deliberately do not open or preview the image.
        return "Screenshot captured."

    def open_folder(self) -> str:
        import os

        os.startfile(str(self.screenshot_folder))
        return "Screenshots folder opened."
