import json
import uuid
from datetime import datetime
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
        """
        Search memory keys and values.

        This uses SQLite LIKE searching for the MVP.
        """

        query = query.strip()

        if not query:
            return []

        search_pattern = (
            f"%{query.lower()}%"
        )

        limit = max(
            1,
            min(int(limit), 100),
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
                  AND (
                      LOWER(memory_key) LIKE ?
                      OR LOWER(memory_value) LIKE ?
                  )
                ORDER BY importance DESC,
                         updated_at DESC
                LIMIT ?
                """,
                (
                    normalized_category,
                    search_pattern,
                    search_pattern,
                    limit,
                ),
            )

        return self.database.fetch_all(
            """
            SELECT *
            FROM memories
            WHERE is_active = 1
              AND (
                  LOWER(memory_key) LIKE ?
                  OR LOWER(memory_value) LIKE ?
              )
            ORDER BY importance DESC,
                     updated_at DESC
            LIMIT ?
            """,
            (
                search_pattern,
                search_pattern,
                limit,
            ),
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