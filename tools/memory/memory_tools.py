from __future__ import annotations

from typing import Any

from core.tool import Tool
from core.tool_schema import (
    ActionSchema,
    PERMISSION_CONFIRM,
)
from memory.memory_manager import MemoryManager
from memory.memory_policy import MemoryPolicy


class MemoryTool(Tool):
    """Read and manage MV.ai's SQLite long-term memories."""

    name = "memory"
    description = (
        "Store, search, update, list, and forget long-term user memories. "
        "Use this for user-requested memories, not passwords or secrets."
    )
    supported_devices = ("laptop",)
    prompt_rules = (
        "Use memory only when the user explicitly asks MV.ai to remember, "
        "recall, update, or forget information.",
        "Never store passwords, API keys, OTPs, banking information, "
        "private keys, or exact home addresses.",
        "Use remember_memory for a new fact and update_memory when replacing "
        "an existing fact.",
    )
    actions = {
        "remember_memory": ActionSchema(
            description="Store a new long-term memory.",
            required_arguments=("key", "value"),
            optional_arguments=("category", "importance"),
            example={
                "key": "preferred_coding_folder",
                "value": "Desktop/MV.ai_V4",
                "category": "folder",
                "importance": 7,
            },
            prompt_rules=(
                "Create a short stable snake_case key.",
                "Do not use this action to overwrite an existing memory.",
            ),
        ),
        "search_memory": ActionSchema(
            description="Search long-term memories by topic or meaning.",
            required_arguments=("query",),
            optional_arguments=("category", "limit"),
            example={
                "query": "MV.ai project",
                "limit": 5,
            },
        ),
        "list_memories": ActionSchema(
            description="List active long-term memories.",
            optional_arguments=("category", "limit"),
            example={},
        ),
        "update_memory": ActionSchema(
            description="Replace an existing long-term memory.",
            required_arguments=("query", "value"),
            optional_arguments=("new_key", "category", "importance"),
            permission=PERMISSION_CONFIRM,
            confirmation_message=(
                "Replace the stored memory matching '{query}' with the new value?"
            ),
            example={
                "query": "preferred coding folder",
                "value": "Documents/MV.ai",
            },
        ),
        "forget_memory": ActionSchema(
            description="Deactivate an existing long-term memory.",
            required_arguments=("query",),
            optional_arguments=("category", "permanent"),
            permission=PERMISSION_CONFIRM,
            confirmation_message="Forget the stored memory matching '{query}'?",
            example={
                "query": "old gym schedule",
                "permanent": False,
            },
        ),
    }

    def __init__(self, memory_manager: MemoryManager | None = None):
        self.memory_manager = memory_manager

    def bind(self, memory_manager: MemoryManager) -> None:
        self.memory_manager = memory_manager

    def _manager(self) -> MemoryManager:
        if self.memory_manager is None:
            raise RuntimeError("The memory tool is not connected to MV.ai's database.")
        return self.memory_manager

    @staticmethod
    def _clean_limit(value: Any, default: int = 10) -> int:
        try:
            return max(1, min(int(value), 100))
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _format_memory(memory: dict[str, Any]) -> str:
        category = str(memory.get("category", "general"))
        key = MemoryManager.display_key(str(memory.get("memory_key", "memory")))
        value = str(memory.get("memory_value", ""))
        return f"[{category}] {key}: {value}"

    @classmethod
    def _format_results(cls, memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "I couldn't find a matching long-term memory."
        return "I found these memories:\n" + "\n".join(
            f"- {cls._format_memory(memory)}"
            for memory in memories
        )

    def execute(self, args=None):
        args = dict(args or {})
        action = str(args.get("action", "")).strip().lower()
        manager = self._manager()

        if action == "remember_memory":
            key = str(args.get("key", "")).strip()
            value = args.get("value")
            category = str(args.get("category", "general")).strip() or "general"
            importance = self._clean_limit(args.get("importance", 5), default=5)
            importance = min(importance, 10)

            MemoryPolicy.validate(key, value)
            existing = manager.find_exact(key, category)
            if existing is not None:
                if str(existing["memory_value"]).strip() == str(value).strip():
                    return "I already remember that."
                return (
                    "A memory with that key already exists. Ask me to update "
                    "it so I can show a confirmation first."
                )

            memory = manager.create_memory(
                key=key,
                value=value,
                category=category,
                importance=importance,
                source="explicit_user_command",
            )
            return "Remembered: " + self._format_memory(memory)

        if action == "search_memory":
            query = str(args.get("query", "")).strip()
            category = str(args.get("category", "")).strip() or None
            limit = self._clean_limit(args.get("limit", 10))
            return self._format_results(
                manager.search_relevant(query, category=category, limit=limit)
            )

        if action == "list_memories":
            category = str(args.get("category", "")).strip() or None
            limit = self._clean_limit(args.get("limit", 30), default=30)
            return self._format_results(
                manager.get_all_memories(category=category, limit=limit)
            )

        if action == "update_memory":
            query = str(args.get("query", "")).strip()
            new_value = args.get("value")
            category = str(args.get("category", "")).strip() or None
            matches = manager.search_relevant(query, category=category, limit=5)
            if not matches:
                return "I couldn't find a memory to update."
            if len(matches) > 1 and (
                matches[0]["relevance_score"] - matches[1]["relevance_score"] < 0.22
            ):
                return (
                    "That matches more than one memory. Please name the exact "
                    "memory key, or edit it from the Memory tab.\n"
                    + self._format_results(matches[:5])
                )

            selected = matches[0]
            new_key = str(args.get("new_key", "")).strip() or None
            new_category = category or selected["category"]
            MemoryPolicy.validate(new_key or selected["memory_key"], new_value)
            updated = manager.update_memory(
                selected["id"],
                key=new_key,
                value=new_value,
                category=new_category,
                importance=args.get("importance"),
                source="explicit_user_command",
            )
            return "Updated: " + self._format_memory(updated)

        if action == "forget_memory":
            query = str(args.get("query", "")).strip()
            category = str(args.get("category", "")).strip() or None
            permanent = bool(args.get("permanent", False))
            matches = manager.search_relevant(query, category=category, limit=5)
            if not matches:
                return "I couldn't find a memory to forget."
            if len(matches) > 1 and (
                matches[0]["relevance_score"] - matches[1]["relevance_score"] < 0.22
            ):
                return (
                    "That matches more than one memory. Please be more specific, "
                    "or delete it from the Memory tab.\n"
                    + self._format_results(matches[:5])
                )

            selected = matches[0]
            forgotten = manager.forget_by_id(selected["id"], permanent=permanent)
            if not forgotten:
                return "That memory was already removed."
            return "Forgotten: " + self._format_memory(selected)

        return f"Unknown memory action: {action or '(missing)'}."
