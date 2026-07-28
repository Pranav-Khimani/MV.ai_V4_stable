from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


class UserProfile:
    """Load and answer questions from MV.ai's editable profile JSON file.

    The file is re-read for every request, so saved edits are available to the
    next command without restarting MV.ai or changing Python code.
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

    def answer_query(self, query: str) -> str | None:
        """Answer common profile questions locally, without calling Gemini.

        Returning ``None`` means the query is not a supported local profile
        question and should continue through the normal AI planner.
        """

        normalized = self._normalize_query(query)
        if not normalized:
            return None

        query_kind = self._classify_query(normalized)
        if query_kind is None:
            return None

        try:
            profile = self.load()
        except ValueError as error:
            return f"I could not read user_profile.json: {error}"

        if not profile:
            return (
                "Your editable profile is empty. Add facts to "
                "user_profile.json and save the file."
            )

        if query_kind == "all":
            return self._describe_profile(profile)

        if query_kind == "name":
            value = self._get_nested(profile, "personal", "name")
            return self._single_fact_answer("name", value)

        if query_kind == "nickname":
            value = self._get_nested(profile, "personal", "nickname")
            return self._single_fact_answer("nickname", value)

        if query_kind == "preferred_name":
            value = self._get_nested(
                profile,
                "personal",
                "preferred_name",
            )
            return self._single_fact_answer("preferred name", value)

        if query_kind == "age":
            value = self._get_nested(profile, "personal", "age")
            return self._single_fact_answer("age", value)

        if query_kind == "projects":
            projects = profile.get("projects")
            if not isinstance(projects, dict) or not projects:
                return (
                    "You have not added any projects to "
                    "user_profile.json yet."
                )
            return self._describe_section("Projects", projects)

        return None

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
    def _classify_query(cls, normalized: str) -> str | None:
        all_patterns = (
            r"^(?:can you )?tell me everything you know about me$",
            r"^everything you know about me$",
            r"^what (?:all )?do you know about me$",
            r"^tell me about myself$",
            r"^who am i$",
        )
        if any(re.fullmatch(pattern, normalized) for pattern in all_patterns):
            return "all"

        if re.fullmatch(
            r"(?:what is|what's|tell me) my (?:full )?name",
            normalized,
        ):
            return "name"

        if re.fullmatch(
            r"(?:what is|what's|tell me) my nick ?name",
            normalized,
        ):
            return "nickname"

        if re.fullmatch(
            r"(?:what is|what's|tell me) my preferred name",
            normalized,
        ):
            return "preferred_name"

        if re.fullmatch(
            r"(?:what is|what's|tell me) my age|how old am i",
            normalized,
        ):
            return "age"

        project_patterns = (
            r"what projects am i building",
            r"what are my projects",
            r"which projects am i building",
            r"tell me my projects",
            r"what is my main project",
            r"what's my main project",
        )
        if any(re.fullmatch(pattern, normalized) for pattern in project_patterns):
            return "projects"

        return None

    @staticmethod
    def _normalize_query(query: str) -> str:
        normalized = str(query).strip().lower()
        normalized = re.sub(r"[^a-z0-9' ]+", " ", normalized)
        normalized = re.sub(r"\babt\b", "about", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    @staticmethod
    def _get_nested(
        profile: dict[str, Any],
        section: str,
        key: str,
    ) -> Any:
        section_value = profile.get(section)
        if not isinstance(section_value, dict):
            return None
        return section_value.get(key)

    @classmethod
    def _single_fact_answer(cls, label: str, value: Any) -> str:
        if not cls._is_meaningful(value):
            return (
                f"Your {label} is not set in user_profile.json yet."
            )

        formatted = cls._format_scalar(value)
        if label == "age":
            return f"You are {formatted} years old."
        return f"Your {label} is {formatted}."

    @classmethod
    def _describe_profile(cls, profile: dict[str, Any]) -> str:
        sections: list[str] = []

        for key, value in profile.items():
            key_text = str(key).strip()
            if not key_text or key_text.startswith("_"):
                continue
            if not cls._is_meaningful(value):
                continue

            if isinstance(value, dict):
                section = cls._describe_section(
                    cls._humanize_key(key_text),
                    value,
                )
                if section:
                    sections.append(section)
            else:
                sections.append(
                    f"{cls._humanize_key(key_text)}: "
                    f"{cls._format_scalar(value)}"
                )

        if not sections:
            return (
                "Your editable profile does not contain any filled-in facts yet."
            )

        return (
            "Here is what I know from your editable profile:\n\n"
            + "\n\n".join(sections)
        )

    @classmethod
    def _describe_section(
        cls,
        title: str,
        values: dict[str, Any],
    ) -> str:
        lines: list[str] = []

        for key, value in values.items():
            key_text = str(key).strip()
            if not key_text or key_text.startswith("_"):
                continue
            if not cls._is_meaningful(value):
                continue

            label = cls._humanize_key(key_text)
            if isinstance(value, dict):
                nested: list[str] = []
                cls._flatten(value, nested)
                if nested:
                    lines.append(f"• {label}: {'; '.join(nested)}")
            elif isinstance(value, list):
                cleaned = [
                    cls._format_scalar(item)
                    for item in value
                    if cls._is_meaningful(item)
                ]
                if cleaned:
                    lines.append(f"• {label}: {', '.join(cleaned)}")
            else:
                lines.append(f"• {label}: {cls._format_scalar(value)}")

        if not lines:
            return ""

        return f"{title}:\n" + "\n".join(lines)

    @staticmethod
    def _humanize_key(key: str) -> str:
        text = re.sub(r"[_\-.]+", " ", key).strip()
        text = re.sub(r"\s+", " ", text)
        return text[:1].upper() + text[1:] if text else key

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
