from __future__ import annotations

import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import ImageGrab

from core.tool import Tool
from core.tool_schema import ActionSchema


class ScreenshotTool(Tool):
    """Capture the Windows desktop and save screenshots locally."""

    name = "screenshot"
    description = (
        "Capture the full desktop, save a PNG screenshot, or open the "
        "MV.ai screenshots folder."
    )
    actions = {
        "capture": ActionSchema(
            description="Capture all connected displays and save a PNG screenshot.",
            optional_arguments=("delay", "open_after_capture"),
            example={"delay": 0, "open_after_capture": True},
            prompt_rules=(
                "Use this action when the user asks to take, capture, save, or create a screenshot.",
                "delay is an optional number of seconds from 0 to 10.",
            ),
        ),
        "open_folder": ActionSchema(
            description="Open the folder containing screenshots created by MV.ai.",
            example={},
            prompt_rules=(
                "Use this action when the user asks to open or show the screenshots folder.",
            ),
        ),
    }
    prompt_rules = (
        "For 'take a screenshot', use action capture.",
        "For 'open my screenshots folder', use action open_folder.",
    )

    def __init__(self) -> None:
        self.screenshot_folder = Path.home() / "Pictures" / "MV.AI Screenshots"
        self.screenshot_folder.mkdir(parents=True, exist_ok=True)

    def execute(self, args: Any = None) -> str:
        args = args if isinstance(args, dict) else {}
        action = str(args.get("action", "capture")).strip().lower()

        try:
            if action == "capture":
                delay = self._safe_delay(args.get("delay", 0))
                open_after_capture = self._as_bool(
                    args.get("open_after_capture", True)
                )
                return self._take_screenshot(delay, open_after_capture)

            if action == "open_folder":
                return self._open_screenshot_folder()

            return f"Unknown screenshot action: {action}"

        except Exception as error:
            return f"I couldn't take the screenshot because: {error}"

    @staticmethod
    def _safe_delay(value: Any) -> float:
        try:
            delay = float(value)
        except (TypeError, ValueError):
            return 0.0
        return max(0.0, min(delay, 10.0))

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() not in {"false", "0", "no", "off"}

    def _take_screenshot(
        self,
        delay: float,
        open_after_capture: bool,
    ) -> str:
        if delay:
            time.sleep(delay)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        screenshot_path = self.screenshot_folder / f"MVAI_Screenshot_{timestamp}.png"

        screenshot = ImageGrab.grab(all_screens=True)
        screenshot.save(screenshot_path, format="PNG")

        if open_after_capture:
            self._open_path(screenshot_path)

        return (
            "Screenshot captured successfully. "
            f"Saved to: {screenshot_path}"
        )

    def _open_screenshot_folder(self) -> str:
        self._open_path(self.screenshot_folder)
        return f"Opened the screenshots folder: {self.screenshot_folder}"

    @staticmethod
    def _open_path(path: Path) -> None:
        if hasattr(os, "startfile"):
            os.startfile(str(path))
            return

        subprocess.Popen(["explorer", str(path)], shell=False)
