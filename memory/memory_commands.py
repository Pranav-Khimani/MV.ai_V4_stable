from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ai.models import TaskPlan, TaskStep
from memory.memory_manager import MemoryManager
from memory.user_profile import UserProfile


@dataclass(frozen=True)
class ParsedMemory:
    key: str
    value: str
    category: str
    importance: int = 5


class MemoryCommandRouter:
    """Parse common memory commands locally, without requiring Gemini."""

    _REMEMBER_PREFIX = re.compile(
        r"^(?:please\s+)?(?:can\s+you\s+)?remember\s+that\s+(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    _UPDATE_PREFIX = re.compile(
        r"^(?:please\s+)?(?:update|change|replace)\s+(.+?)\s+"
        r"(?:to|with)\s+(.+)$",
        re.IGNORECASE | re.DOTALL,
    )
    _FORGET_PREFIX = re.compile(
        r"^(?:please\s+)?(?:forget|remove|delete)\s+"
        r"(?:(?:the|that)\s+)?(?:memory\s+)?(?:about\s+)?(.+)$",
        re.IGNORECASE | re.DOTALL,
    )

    def __init__(
        self,
        memory_manager: MemoryManager,
        user_profile: UserProfile | None = None,
    ) -> None:
        self.memory = memory_manager
        self.user_profile = user_profile

    def create_plan(self, command: str) -> TaskPlan | None:
        normalized = " ".join(str(command).strip().split())
        if not normalized:
            return None

        remember_match = self._REMEMBER_PREFIX.fullmatch(normalized)
        if remember_match:
            parsed = self._parse_remember_clause(remember_match.group(1))
            existing = self.memory.find_exact(parsed.key, parsed.category)
            if existing is None:
                return self._step_plan(
                    goal="Remember information",
                    action="remember_memory",
                    args={
                        "key": parsed.key,
                        "value": parsed.value,
                        "category": parsed.category,
                        "importance": parsed.importance,
                    },
                    description=f"Remember {MemoryManager.display_key(parsed.key)}.",
                )

            if str(existing["memory_value"]).strip().casefold() == parsed.value.casefold():
                return TaskPlan(
                    goal="Remember information",
                    message="I already remember that.",
                )

            return self._step_plan(
                goal="Update remembered information",
                action="update_memory",
                args={
                    "query": existing["memory_key"],
                    "value": parsed.value,
                    "category": existing["category"],
                    "importance": parsed.importance,
                },
                description=(
                    "Replace the existing memory about "
                    f"{MemoryManager.display_key(existing['memory_key'])}."
                ),
            )

        update_match = self._UPDATE_PREFIX.fullmatch(normalized)
        if update_match:
            query = self._clean_fragment(update_match.group(1))
            value = self._clean_fragment(update_match.group(2))
            if not query or not value:
                return TaskPlan(
                    goal="Update memory",
                    message=(
                        "Tell me which memory to update and the new value. "
                        "Example: Update my preferred editor to VS Code."
                    ),
                )
            matches = self.memory.search_relevant(query, limit=5)
            if not matches:
                return TaskPlan(
                    goal="Update memory",
                    message=(
                        "I couldn't find a matching long-term memory. "
                        "Use 'Remember that ...' to create it first."
                    ),
                )
            if self._ambiguous(matches):
                return TaskPlan(
                    goal="Update memory",
                    message=self._ambiguity_message("update", matches),
                )
            selected = matches[0]
            return self._step_plan(
                goal="Update memory",
                action="update_memory",
                args={
                    "query": selected["memory_key"],
                    "value": value,
                    "category": selected["category"],
                },
                description=(
                    "Update the memory about "
                    f"{MemoryManager.display_key(selected['memory_key'])}."
                ),
            )

        forget_match = self._FORGET_PREFIX.fullmatch(normalized)
        if forget_match:
            query = self._clean_fragment(forget_match.group(1))
            matches = self.memory.search_relevant(query, limit=5)
            if not matches:
                return TaskPlan(
                    goal="Forget memory",
                    message="I couldn't find a matching long-term memory.",
                )
            if self._ambiguous(matches):
                return TaskPlan(
                    goal="Forget memory",
                    message=self._ambiguity_message("forget", matches),
                )
            selected = matches[0]
            return self._step_plan(
                goal="Forget memory",
                action="forget_memory",
                args={
                    "query": selected["memory_key"],
                    "category": selected["category"],
                    "permanent": False,
                },
                description=(
                    "Forget the memory about "
                    f"{MemoryManager.display_key(selected['memory_key'])}."
                ),
            )

        recall = self._parse_recall(normalized)
        if recall is not None:
            if recall == "__all__":
                memories = self.memory.get_all_memories(limit=50)
                return TaskPlan(
                    goal="Recall memories",
                    message=self._combined_memory_summary(memories),
                )
            return self._step_plan(
                goal="Search long-term memory",
                action="search_memory",
                args={"query": recall, "limit": 10},
                description=f"Search memories about {recall}.",
            )

        return None

    @staticmethod
    def _step_plan(
        *,
        goal: str,
        action: str,
        args: dict[str, Any],
        description: str,
    ) -> TaskPlan:
        return TaskPlan(
            goal=goal,
            steps=[
                TaskStep(
                    device="laptop",
                    tool="memory",
                    args={"action": action, **args},
                    description=description,
                )
            ],
        )

    def _parse_recall(self, command: str) -> str | None:
        lowered = command.lower().strip(" .?!")
        all_patterns = (
            r"(?:what|which) (?:all )?do you remember about me",
            r"tell me (?:all|everything) you remember about me",
            r"show (?:me )?my (?:long term )?memories",
            r"list (?:my )?(?:long term )?memories",
            r"what do you remember",
        )
        if any(re.fullmatch(pattern, lowered) for pattern in all_patterns):
            return "__all__"

        patterns = (
            r"what do you remember about (.+)",
            r"tell me what you remember about (.+)",
            r"search (?:your )?memory for (.+)",
            r"search memories for (.+)",
            r"recall (?:what you know about )?(.+)",
            r"do you remember (.+)",
        )
        for pattern in patterns:
            match = re.fullmatch(pattern, lowered)
            if match:
                query = self._clean_fragment(match.group(1))
                return query or None
        return None

    def _parse_remember_clause(self, clause: str) -> ParsedMemory:
        clean = self._clean_fragment(clause)

        prefer_match = re.fullmatch(
            r"i\s+(?:prefer|like|want)\s+(.+)",
            clean,
            flags=re.IGNORECASE,
        )
        if prefer_match:
            value = self._clean_fragment(prefer_match.group(1))
            return ParsedMemory(
                key=self._derive_preference_key(value),
                value=value,
                category="preference",
                importance=7,
            )

        relationship_patterns = (
            r"(?:my\s+)?(.+?)\s+(?:is|are)\s+(?:located\s+)?(?:in|at)\s+(.+)",
            r"(?:my\s+)?(.+?)\s+(?:is|are|=)\s+(.+)",
            r"i\s+use\s+(.+?)\s+for\s+(.+)",
            r"i\s+am\s+(.+)",
            r"i\s+have\s+(.+)",
        )
        for index, pattern in enumerate(relationship_patterns):
            match = re.fullmatch(pattern, clean, flags=re.IGNORECASE)
            if not match:
                continue
            if index == 2:
                tool = self._clean_fragment(match.group(1))
                purpose = self._clean_fragment(match.group(2))
                subject = f"preferred {purpose} tool"
                value = tool
            elif index == 3:
                subject = "personal status"
                value = self._clean_fragment(match.group(1))
            elif index == 4:
                subject = self._derive_key_text(match.group(1))
                value = self._clean_fragment(match.group(1))
            else:
                subject = self._clean_fragment(match.group(1))
                value = self._clean_fragment(match.group(2))

            key = MemoryManager.normalize_key(self._derive_key_text(subject))
            category = self._infer_category(subject, value)
            return ParsedMemory(
                key=key,
                value=value,
                category=category,
                importance=self._infer_importance(category),
            )

        key_text = self._derive_key_text(clean)
        return ParsedMemory(
            key=MemoryManager.normalize_key(key_text),
            value=clean,
            category=self._infer_category(key_text, clean),
            importance=5,
        )

    @staticmethod
    def _clean_fragment(text: str) -> str:
        cleaned = " ".join(str(text).strip().split())
        cleaned = re.sub(r"^[,:;\-]+", "", cleaned).strip()
        return cleaned.rstrip(" .?!")

    @staticmethod
    def _derive_key_text(text: str) -> str:
        lowered = str(text).lower()
        lowered = re.sub(r"\b(?:my|the|a|an|that|this|some)\b", " ", lowered)
        words = re.findall(r"[a-z0-9]+", lowered)
        stop = {"i", "have", "am", "are", "is", "in", "at", "to", "of", "for"}
        useful = [word for word in words if word not in stop]
        return " ".join(useful[:6]) or "memory note"

    @classmethod
    def _derive_preference_key(cls, value: str) -> str:
        lowered = value.lower()
        if any(word in lowered for word in ("answer", "response", "reply")):
            return "preferred_response_style"
        if any(word in lowered for word in ("editor", "vscode", "visual studio")):
            return "preferred_editor"
        if any(word in lowered for word in ("food", "diet", "meal")):
            return "food_preference"
        return MemoryManager.normalize_key("preferred " + cls._derive_key_text(value))

    @staticmethod
    def _infer_category(subject: str, value: str) -> str:
        text = f"{subject} {value}".lower()
        categories = (
            ("folder", ("folder", "directory", "path", "documents", "desktop", "downloads")),
            ("project", ("project", "mv.ai", "mvai", "gnosis", "app", "software")),
            ("preference", ("prefer", "preferred", "style", "favorite", "favourite", "like")),
            ("routine", ("routine", "schedule", "daily", "weekly", "gym", "workout", "habit")),
            ("application", ("editor", "vscode", "chrome", "application", "app")),
            ("device", ("laptop", "phone", "microphone", "device", "computer")),
            ("personal", ("name", "nickname", "birthday", "age", "college", "school", "goal")),
        )
        for category, words in categories:
            if any(word in text for word in words):
                return category
        return "general"

    @staticmethod
    def _infer_importance(category: str) -> int:
        return {
            "personal": 8,
            "preference": 7,
            "project": 8,
            "folder": 7,
            "routine": 6,
            "application": 5,
            "device": 5,
        }.get(category, 5)

    @staticmethod
    def _ambiguous(matches: list[dict[str, Any]]) -> bool:
        if len(matches) < 2:
            return False
        first = float(matches[0].get("relevance_score", 0.0))
        second = float(matches[1].get("relevance_score", 0.0))
        return first < 0.65 or first - second < 0.22

    @staticmethod
    def _ambiguity_message(action: str, matches: list[dict[str, Any]]) -> str:
        lines = [
            f"That matches several memories. Tell me which one to {action}:"
        ]
        for memory in matches[:5]:
            key = MemoryManager.display_key(memory["memory_key"])
            lines.append(
                f"- [{memory['category']}] {key}: {memory['memory_value']}"
            )
        return "\n".join(lines)

    def _combined_memory_summary(self, memories: list[dict[str, Any]]) -> str:
        sections: list[str] = []
        if self.user_profile is not None:
            profile_context = self.user_profile.get_context()
            if profile_context and "No editable" not in profile_context:
                readable = profile_context.replace("EDITABLE USER PROFILE:\n", "")
                sections.append("Editable profile:\n" + readable)

        if memories:
            lines = ["Learned long-term memories:"]
            for memory in memories:
                key = MemoryManager.display_key(memory["memory_key"])
                lines.append(
                    f"- [{memory['category']}] {key}: {memory['memory_value']}"
                )
            sections.append("\n".join(lines))
        else:
            sections.append("No learned long-term memories are stored yet.")

        return "\n\n".join(sections)
