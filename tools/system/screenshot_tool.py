from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QPainter, QPixmap

from core.tool import Tool
from core.tool_schema import ActionSchema


class ScreenshotTool(Tool):
    """Capture every connected display and save the result as a PNG."""

    name = "screenshot"
    description = (
        "Capture the Windows desktop as a PNG screenshot or open the "
        "MV.AI screenshots folder."
    )
    actions = {
        "capture": ActionSchema(
            description="Capture all connected screens and save a PNG file.",
            optional_arguments=("open_after_capture",),
            example={"open_after_capture": True},
        ),
        "open_folder": ActionSchema(
            description="Open the folder containing screenshots.",
            example={},
        ),
    }
    prompt_rules = (
        "Use capture when the user asks to take a screenshot or capture the screen.",
        "Use open_folder when the user asks to open or show the screenshots folder.",
    )

    def __init__(self) -> None:
        self.screenshot_folder = Path.home() / "Pictures" / "MV.AI Screenshots"
        self.screenshot_folder.mkdir(parents=True, exist_ok=True)

    def execute(self, args: Any = None) -> str:
        args = args if isinstance(args, dict) else {}
        action = str(args.get("action", "capture")).strip().lower()

        if action == "capture":
            open_after_capture = self._as_bool(
                args.get("open_after_capture", True)
            )
            return self._capture(open_after_capture)

        if action == "open_folder":
            os.startfile(str(self.screenshot_folder))
            return f"Opened screenshots folder: {self.screenshot_folder}"

        return f"Unknown screenshot action: {action}"

    def _capture(self, open_after_capture: bool) -> str:
        app = QGuiApplication.instance()
        if app is None:
            raise RuntimeError("The MV.AI window system is not running.")

        screens = app.screens()
        if not screens:
            raise RuntimeError("Windows did not report any connected display.")

        virtual_geometry = QRect()
        for screen in screens:
            virtual_geometry = virtual_geometry.united(screen.geometry())

        canvas = QPixmap(virtual_geometry.size())
        canvas.fill()

        painter = QPainter(canvas)
        try:
            for screen in screens:
                shot = screen.grabWindow(0)
                position = screen.geometry().topLeft() - virtual_geometry.topLeft()
                painter.drawPixmap(position, shot)
        finally:
            painter.end()

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = self.screenshot_folder / f"MVAI_Screenshot_{timestamp}.png"

        if not canvas.save(str(path), "PNG"):
            raise RuntimeError("Windows could not save the screenshot file.")

        if open_after_capture:
            os.startfile(str(path))

        return f"Screenshot captured and saved to: {path}"

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() not in {"0", "false", "no", "off"}
        return bool(value)
