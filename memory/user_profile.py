from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class UserProfile:
    """Load MV.ai's manually editable user-profile JSON file.

    The file is re-read whenever context is requested, so saved edits are
    available to the next command without changing Python code.
    """

    MAX_FILE_BYTES = 64 * 1024

    def __init__(self, profile_path: str | Path):
        self.profile_path = Path(profile_path)

    def load(self) -> dict[str, Any]:
        """Return the profile object, raising a clear error if it is invalid."""

        if not self.profile_path.exists():
            return {}

        size = self.profile_path.stat().st_size
        if size > self.MAX_FILE_BYTES:
            raise ValueError(
                "user_profile.json is too large. Keep it below 64 KB."
            )

        try:
            raw_text = self.profile_path.read_text(encoding="utf-8")
            data = json.loads(raw_text)
        except json.JSONDecodeError as error:
            raise ValueError(
                "user_profile.json contains invalid JSON at "
                f"line {error.lineno}, column {error.colno}: {error.msg}"
            ) from error
        except OSError as error:
            raise ValueError(
                f"Could not read user_profile.json: {error}"
            ) from error

        if not isinstance(data, dict):
            raise ValueError(
                "user_profile.json must contain one JSON object at its root."
            )

        return data

    def get_context(self) -> str:
        """Return a compact facts-only version for the AI prompt."""

        try:
            profile = self.load()
        except ValueError as error:
            return f"USER PROFILE ERROR: {error}"

        facts: list[str] = []
        self._flatten(profile, facts)

        if not facts:
            return "No editable user-profile facts are currently stored."

        return "EDITABLE USER PROFILE:\n" + "\n".join(
            f"- {fact}" for fact in facts
        )

    def get_status(self) -> dict[str, Any]:
        """Return basic profile status for diagnostics."""

        try:
            profile = self.load()
            facts: list[str] = []
            self._flatten(profile, facts)
            return {
                "ready": True,
                "path": str(self.profile_path),
                "fact_count": len(facts),
            }
        except ValueError as error:
            return {
                "ready": False,
                "path": str(self.profile_path),
                "error": str(error),
            }

    @classmethod
    def _flatten(
        cls,
        value: Any,
        output: list[str],
        prefix: str = "",
    ) -> None:
        """Flatten nested JSON into readable key/value facts."""

        if isinstance(value, dict):
            for key, child in value.items():
                key_text = str(key).strip()
                if not key_text or key_text.startswith("_"):
                    continue

                child_prefix = (
                    f"{prefix}.{key_text}" if prefix else key_text
                )
                cls._flatten(child, output, child_prefix)
            return

        if isinstance(value, list):
            cleaned = [
                cls._format_scalar(item)
                for item in value
                if cls._is_meaningful(item)
            ]
            if cleaned and prefix:
                output.append(f"{prefix}: {', '.join(cleaned)}")
            return

        if prefix and cls._is_meaningful(value):
            output.append(f"{prefix}: {cls._format_scalar(value)}")

    @staticmethod
    def _is_meaningful(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, (dict, list)):
            return bool(value)
        return True

    @staticmethod
    def _format_scalar(value: Any) -> str:
        if isinstance(value, bool):
            return "yes" if value else "no"
        return str(value).strip()
