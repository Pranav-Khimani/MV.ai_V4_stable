import json
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher
from typing import Any

from memory.database import MemoryDatabase


class MemoryManager:
    """
    High-level long-term memory system for MV.AI.

    Supports:
    - Remembering facts and preferences
    - Recalling stored memories
    - Searching memories
    - Forgetting memories
    - Conversation history
    - Command history
    - Sessions
    """

    VALID_CATEGORIES = {
        "general",
        "personal",
        "preference",
        "project",
        "folder",
        "application",
        "routine",
        "device",
    }

    def __init__(
        self,
        database_path: str = "data/mv_memory.db",
    ):
        self.database = MemoryDatabase(
            database_path=database_path,
        )

        self.session_id = self.create_session()

    @staticmethod
    def now() -> str:
        """
        Return the current local time as an ISO string.
        """

        return datetime.now().isoformat(
            timespec="seconds"
        )

    @staticmethod
    def normalize_key(key: str) -> str:
        """
        Normalize memory keys for consistent storage.
        """

        normalized = key.strip().lower()

        normalized = "_".join(
            normalized.split()
        )

        return normalized

    def normalize_category(
        self,
        category: str,
    ) -> str:
        """
        Normalize memory categories.

        Unknown categories are allowed but converted
        into lowercase underscore format.
        """

        normalized = category.strip().lower()

        normalized = "_".join(
            normalized.split()
        )

        return normalized or "general"

    @staticmethod
    def display_key(key: str) -> str:
        """Turn an internal memory key into readable text."""

        return str(key).replace("_", " ").strip()

    def get_memory_by_id(
        self,
        memory_id: int,
        include_inactive: bool = False,
    ) -> dict[str, Any] | None:
        """Return one memory by database ID."""

        query = "SELECT * FROM memories WHERE id = ?"
        parameters: tuple[Any, ...] = (int(memory_id),)
        if not include_inactive:
            query += " AND is_active = 1"
        query += " LIMIT 1"
        return self.database.fetch_one(query, parameters)

    def find_exact(
        self,
        key: str,
        category: str | None = None,
    ) -> dict[str, Any] | None:
        """Find an active memory by its normalized key."""

        normalized_key = self.normalize_key(key)
        if category:
            return self.database.fetch_one(
                """
                SELECT * FROM memories
                WHERE memory_key = ?
                  AND category = ?
                  AND is_active = 1
                LIMIT 1
                """,
                (normalized_key, self.normalize_category(category)),
            )

        return self.database.fetch_one(
            """
            SELECT * FROM memories
            WHERE memory_key = ?
              AND is_active = 1
            ORDER BY importance DESC, updated_at DESC
            LIMIT 1
            """,
            (normalized_key,),
        )

    def create_memory(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: int = 5,
        source: str = "user",
    ) -> dict[str, Any]:
        """Create a memory without silently overwriting an existing one."""

        existing = self.find_exact(key, category)
        if existing is not None:
            raise ValueError(
                "A memory with that key already exists in this category."
            )

        return self.remember(
            key=key,
            value=value,
            category=category,
            importance=importance,
            source=source,
        )

    def update_memory(
        self,
        memory_id: int,
        *,
        key: str | None = None,
        value: Any | None = None,
        category: str | None = None,
        importance: int | None = None,
        source: str = "user",
    ) -> dict[str, Any]:
        """Update one memory by ID and return the refreshed row."""

        current = self.get_memory_by_id(memory_id)
        if current is None:
            raise ValueError("That memory no longer exists.")

        new_key = self.normalize_key(key or current["memory_key"])
        new_category = self.normalize_category(category or current["category"])
        new_value = str(
            current["memory_value"] if value is None else value
        ).strip()
        new_importance = current["importance"] if importance is None else max(
            1, min(int(importance), 10)
        )

        if not new_key:
            raise ValueError("Memory key cannot be empty.")
        if not new_value:
            raise ValueError("Memory value cannot be empty.")

        duplicate = self.database.fetch_one(
            """
            SELECT id FROM memories
            WHERE category = ?
              AND memory_key = ?
              AND id != ?
              AND is_active = 1
            LIMIT 1
            """,
            (new_category, new_key, int(memory_id)),
        )
        if duplicate is not None:
            raise ValueError(
                "Another active memory already uses that key and category."
            )

        self.database.execute(
            """
            UPDATE memories
            SET category = ?,
                memory_key = ?,
                memory_value = ?,
                importance = ?,
                source = ?,
                updated_at = ?,
                is_active = 1
            WHERE id = ?
            """,
            (
                new_category,
                new_key,
                new_value,
                new_importance,
                source,
                self.now(),
                int(memory_id),
            ),
        )
        refreshed = self.get_memory_by_id(memory_id)
        if refreshed is None:
            raise RuntimeError("The memory could not be reloaded after updating.")
        return refreshed

    def forget_by_id(
        self,
        memory_id: int,
        permanent: bool = False,
    ) -> bool:
        """Deactivate or permanently delete one memory by ID."""

        existing = self.get_memory_by_id(memory_id)
        if existing is None:
            return False

        if permanent:
            self.database.execute(
                "DELETE FROM memories WHERE id = ?",
                (int(memory_id),),
            )
        else:
            self.database.execute(
                """
                UPDATE memories
                SET is_active = 0, updated_at = ?
                WHERE id = ?
                """,
                (self.now(), int(memory_id)),
            )
        return True

    @staticmethod
    def _search_tokens(text: str) -> set[str]:
        stop_words = {
            "a", "an", "and", "are", "about", "at", "be", "do",
            "for", "from", "i", "in", "is", "it", "me", "my",
            "of", "on", "that", "the", "this", "to", "what",
            "where", "you", "your",
        }
        return {
            token
            for token in re.findall(r"[a-z0-9]+", text.lower())
            if token not in stop_words and len(token) > 1
        }

    @classmethod
    def _expanded_tokens(cls, text: str) -> set[str]:
        tokens = cls._search_tokens(text)
        synonym_groups = (
            {"folder", "directory", "path", "location"},
            {"college", "school", "education", "class"},
            {"gym", "workout", "exercise", "fitness"},
            {"editor", "vscode", "coding", "development"},
            {"project", "app", "software", "mvai", "assistant"},
            {"preference", "prefer", "style", "choice"},
            {"name", "nickname", "called", "identity"},
            {"routine", "schedule", "habit", "daily"},
        )
        expanded = set(tokens)
        for group in synonym_groups:
            if tokens.intersection(group):
                expanded.update(group)
        return expanded

    def search_relevant(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
        minimum_score: float = 0.18,
    ) -> list[dict[str, Any]]:
        """Rank memories using exact, token, synonym, and fuzzy matching."""

        query = str(query).strip()
        if not query:
            return []

        candidates = self.get_all_memories(category=category, limit=500)
        query_lower = query.lower()
        query_tokens = self._expanded_tokens(query)
        ranked: list[dict[str, Any]] = []

        for memory in candidates:
            key_text = self.display_key(memory["memory_key"])
            value_text = str(memory["memory_value"])
            category_text = str(memory["category"])
            haystack = f"{key_text} {value_text} {category_text}".lower()
            candidate_tokens = self._expanded_tokens(haystack)

            score = 0.0
            if query_lower == key_text.lower():
                score += 1.25
            if query_lower in key_text.lower():
                score += 0.75
            if query_lower in value_text.lower():
                score += 0.55
            if query_lower in haystack:
                score += 0.25

            if query_tokens:
                overlap = len(query_tokens.intersection(candidate_tokens))
                score += 0.9 * overlap / max(1, len(query_tokens))

            score += 0.35 * SequenceMatcher(
                None, query_lower, key_text.lower()
            ).ratio()
            score += 0.15 * SequenceMatcher(
                None, query_lower, value_text.lower()
            ).ratio()
            score += min(int(memory.get("importance", 5)), 10) * 0.005

            if score >= minimum_score:
                item = dict(memory)
                item["relevance_score"] = round(score, 4)
                ranked.append(item)

        ranked.sort(
            key=lambda item: (
                item["relevance_score"],
                item.get("importance", 0),
                item.get("updated_at", ""),
            ),
            reverse=True,
        )
        return ranked[: max(1, min(int(limit), 100))]

    def create_session(
        self,
        title: str | None = None,
    ) -> str:
        """
        Create a new conversation session.
        """

        session_id = str(uuid.uuid4())

        self.database.execute(
            """
            INSERT INTO sessions (
                id,
                started_at,
                title,
                message_count
            )
            VALUES (?, ?, ?, 0)
            """,
            (
                session_id,
                self.now(),
                title,
            ),
        )

        return session_id

    def end_session(self) -> None:
        """
        Mark the current session as ended.
        """

        self.database.execute(
            """
            UPDATE sessions
            SET ended_at = ?
            WHERE id = ?
            """,
            (
                self.now(),
                self.session_id,
            ),
        )


                        

    def remember(
        self,
        key: str,
        value: Any,
        category: str = "general",
        importance: int = 5,
        source: str = "user",
    ) -> dict[str, Any]:
        """
        Store or update a long-term memory.

        Example:
            remember(
                key="name",
                value="Pranav",
                category="personal",
            )
        """

        if not isinstance(key, str) or not key.strip():
            raise ValueError(
                "Memory key cannot be empty."
            )

        if value is None:
            raise ValueError(
                "Memory value cannot be None."
            )

        normalized_key = self.normalize_key(key)
        normalized_category = self.normalize_category(
            category
        )

        importance = max(
            1,
            min(int(importance), 10),
        )

        value_text = str(value).strip()
        if not value_text:
            raise ValueError(
                "Memory value cannot be empty."
            )
        current_time = self.now()

        existing = self.database.fetch_one(
            """
            SELECT id
            FROM memories
            WHERE category = ?
              AND memory_key = ?
            """,
            (
                normalized_category,
                normalized_key,
            ),
        )

        if existing:
            self.database.execute(
                """
                UPDATE memories
                SET memory_value = ?,
                    importance = ?,
                    source = ?,
                    updated_at = ?,
                    is_active = 1
                WHERE category = ?
                  AND memory_key = ?
                """,
                (
                    value_text,
                    importance,
                    source,
                    current_time,
                    normalized_category,
                    normalized_key,
                ),
            )

        else:
            self.database.execute(
                """
                INSERT INTO memories (
                    category,
                    memory_key,
                    memory_value,
                    importance,
                    source,
                    created_at,
                    updated_at,
                    is_active
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    normalized_category,
                    normalized_key,
                    value_text,
                    importance,
                    source,
                    current_time,
                    current_time,
                ),
            )

        return self.recall(
            key=normalized_key,
            category=normalized_category,
        ) or {}

    def recall(
        self,
        key: str,
        category: str | None = None,
    ) -> dict[str, Any] | None:
        """
        Recall one memory by key.

        If category is omitted, the most important and
        recently updated matching memory is returned.
        """

        normalized_key = self.normalize_key(key)

        if category:
            normalized_category = self.normalize_category(
                category
            )

            memory = self.database.fetch_one(
                """
                SELECT *
                FROM memories
                WHERE memory_key = ?
                  AND category = ?
                  AND is_active = 1
                LIMIT 1
                """,
                (
                    normalized_key,
                    normalized_category,
                ),
            )

        else:
            memory = self.database.fetch_one(
                """
                SELECT *
                FROM memories
                WHERE memory_key = ?
                  AND is_active = 1
                ORDER BY importance DESC,
                         updated_at DESC
                LIMIT 1
                """,
                (normalized_key,),
            )

        if memory is None:
            return None

        self.database.execute(
            """
            UPDATE memories
            SET access_count = access_count + 1,
                last_accessed_at = ?
            WHERE id = ?
            """,
            (
                self.now(),
                memory["id"],
            ),
        )

        memory["access_count"] += 1
        memory["last_accessed_at"] = self.now()

        return memory

    def forget(
        self,
        key: str,
        category: str | None = None,
        permanent: bool = False,
    ) -> bool:
        """
        Forget a memory.

        By default, the memory is deactivated instead of
        permanently deleted.
        """

        normalized_key = self.normalize_key(key)

        if category:
            normalized_category = self.normalize_category(
                category
            )

            conditions = (
                "memory_key = ? AND category = ?"
            )

            parameters = (
                normalized_key,
                normalized_category,
            )

        else:
            conditions = "memory_key = ?"
            parameters = (normalized_key,)

        existing = self.database.fetch_one(
            f"""
            SELECT id
            FROM memories
            WHERE {conditions}
              AND is_active = 1
            LIMIT 1
            """,
            parameters,
        )

        if existing is None:
            return False

        if permanent:
            self.database.execute(
                f"""
                DELETE FROM memories
                WHERE {conditions}
                """,
                parameters,
            )

        else:
            self.database.execute(
                f"""
                UPDATE memories
                SET is_active = 0,
                    updated_at = ?
                WHERE {conditions}
                """,
                (
                    self.now(),
                    *parameters,
                ),
            )

        return True

    def search(
        self,
        query: str,
        category: str | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        """Search memories with ranked fuzzy and synonym matching."""

        return self.search_relevant(
            query=query,
            category=category,
            limit=limit,
        )

    def get_all_memories(
        self,
        category: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Return active memories.
        """

        limit = max(
            1,
            min(int(limit), 500),
        )

        if category:
            normalized_category = self.normalize_category(
                category
            )

            return self.database.fetch_all(
                """
                SELECT *
                FROM memories
                WHERE is_active = 1
                  AND category = ?
                ORDER BY importance DESC,
                         updated_at DESC
                LIMIT ?
                """,
                (
                    normalized_category,
                    limit,
                ),
            )

        return self.database.fetch_all(
            """
            SELECT *
            FROM memories
            WHERE is_active = 1
            ORDER BY importance DESC,
                     updated_at DESC
            LIMIT ?
            """,
            (limit,),
        )

    def add_conversation_message(
        self,
        role: str,
        content: str,
        attachments: list[dict[str, Any]] | None = None,
    ) -> int:
        """
        Store a user, assistant, or system message.
        """

        valid_roles = {
            "user",
            "assistant",
            "system",
        }

        normalized_role = role.strip().lower()

        if normalized_role not in valid_roles:
            raise ValueError(
                f"Invalid conversation role: {role}"
            )

        content = content.strip()
        attachments = attachments or []

        if not content and not attachments:
            raise ValueError(
                "Conversation content and attachments cannot both be empty."
            )

        attachments_json = json.dumps(attachments, ensure_ascii=False)

        message_id = self.database.execute(
            """
            INSERT INTO conversations (
                session_id,
                role,
                content,
                created_at,
                attachments_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                self.session_id,
                normalized_role,
                content,
                self.now(),
                attachments_json,
            ),
        )

        self.database.execute(
            """
            UPDATE sessions
            SET message_count = message_count + 1
            WHERE id = ?
            """,
            (self.session_id,),
        )

        return message_id

    def get_conversation_history(
        self,
        limit: int = 20,
        session_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Return recent messages for a session.
        """

        selected_session = (
            session_id
            or self.session_id
        )

        limit = max(
            1,
            min(int(limit), 500),
        )

        messages = self.database.fetch_all(
            """
            SELECT *
            FROM conversations
            WHERE session_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (
                selected_session,
                limit,
            ),
        )

        messages.reverse()

        for message in messages:
            raw_attachments = message.get("attachments_json") or "[]"
            try:
                attachments = json.loads(raw_attachments)
                if not isinstance(attachments, list):
                    attachments = []
            except (TypeError, json.JSONDecodeError):
                attachments = []
            message["attachments"] = attachments

        return messages

    def log_command(
        self,
        command: str,
        success: bool,
        response: str | None = None,
        error: str | None = None,
    ) -> int:
        """
        Store a command execution result.
        """

        return self.database.execute(
            """
            INSERT INTO command_history (
                command,
                success,
                response,
                error,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                command.strip(),
                int(success),
                response,
                error,
                self.now(),
            ),
        )

    def get_recent_commands(
        self,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Return recently executed commands.
        """

        limit = max(
            1,
            min(int(limit), 200),
        )

        return self.database.fetch_all(
            """
            SELECT *
            FROM command_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )

    def get_memory_context(
        self,
        limit: int = 20,
    ) -> str:
        """
        Build a compact text block that can later be
        inserted into Gemini's prompt.
        """

        memories = self.get_all_memories(
            limit=limit
        )

        if not memories:
            return "No long-term memories are stored."

        lines = [
            "Stored long-term memories:"
        ]

        for memory in memories:
            lines.append(
                "- "
                f"[{memory['category']}] "
                f"{memory['memory_key']}: "
                f"{memory['memory_value']}"
            )

        return "\n".join(lines)