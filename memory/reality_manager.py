from __future__ import annotations

from datetime import datetime
from typing import Any


class RealityManager:
    """
    Handles MV.AI conversation sessions ("realities").

    This class uses the existing MemoryManager database and does
    not create a second database or replace the current memory system.
    """

    def __init__(self, memory_manager):
        self.memory = memory_manager

    @staticmethod
    def _make_title(message: str, max_words: int = 7) -> str:
        cleaned = " ".join(message.strip().split())

        if not cleaned:
            return "New Reality"

        words = cleaned.split()
        title = " ".join(words[:max_words]).strip(
            " .,!?:;-_"
        )

        if len(words) > max_words:
            title += "…"

        if len(title) > 52:
            title = title[:49].rstrip() + "…"

        if title:
            title = title[0].upper() + title[1:]

        return title or "New Reality"

    @staticmethod
    def _format_subtitle(
        last_activity: str | None,
        message_count: int,
    ) -> str:
        try:
            activity = datetime.fromisoformat(
                last_activity or ""
            )
        except (TypeError, ValueError):
            activity = datetime.now()

        today = datetime.now().date()
        activity_date = activity.date()
        day_difference = (
            today - activity_date
        ).days

        if day_difference == 0:
            day_text = "Today"
        elif day_difference == 1:
            day_text = "Yesterday"
        elif 1 < day_difference < 7:
            day_text = activity.strftime("%A")
        else:
            day_text = activity.strftime("%d %b %Y")

        message_word = (
            "message"
            if message_count == 1
            else "messages"
        )

        return (
            f"{day_text} • "
            f"{message_count} {message_word}"
        )

    def create_new_reality(self) -> str:
        try:
            self.memory.end_session()
        except Exception:
            pass

        self.memory.session_id = (
            self.memory.create_session()
        )

        return self.memory.session_id

    def ensure_current_title(
        self,
        first_user_message: str,
    ) -> None:
        current = self.memory.database.fetch_one(
            """
            SELECT title
            FROM sessions
            WHERE id = ?
            """,
            (self.memory.session_id,),
        )

        if current is None:
            return

        existing_title = (
            current.get("title") or ""
        ).strip()

        if existing_title:
            return

        title = self._make_title(
            first_user_message
        )

        self.memory.database.execute(
            """
            UPDATE sessions
            SET title = ?
            WHERE id = ?
            """,
            (
                title,
                self.memory.session_id,
            ),
        )

    def get_recent_realities(
        self,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        limit = max(
            1,
            min(int(limit), 100),
        )

        rows = self.memory.database.fetch_all(
            """
            SELECT
                sessions.id,
                sessions.title,
                sessions.started_at,
                sessions.ended_at,
                sessions.message_count,
                COALESCE(
                    MAX(conversations.created_at),
                    sessions.started_at
                ) AS last_activity
            FROM sessions
            LEFT JOIN conversations
                ON conversations.session_id = sessions.id
            WHERE sessions.message_count > 0
            GROUP BY sessions.id
            ORDER BY last_activity DESC
            LIMIT ?
            """,
            (limit,),
        )

        realities = []

        for row in rows:
            message_count = int(
                row.get("message_count") or 0
            )

            realities.append(
                {
                    "id": row["id"],
                    "title": (
                        row.get("title")
                        or "New Reality"
                    ),
                    "subtitle": self._format_subtitle(
                        row.get("last_activity"),
                        message_count,
                    ),
                    "message_count": message_count,
                    "started_at": row.get(
                        "started_at"
                    ),
                    "last_activity": row.get(
                        "last_activity"
                    ),
                }
            )

        return realities

    def load_reality(
        self,
        session_id: str,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        session = self.memory.database.fetch_one(
            """
            SELECT id
            FROM sessions
            WHERE id = ?
            """,
            (session_id,),
        )

        if session is None:
            raise ValueError(
                "The selected reality no longer exists."
            )

        self.memory.session_id = session_id

        return self.memory.get_conversation_history(
            limit=limit,
            session_id=session_id,
        )

    def clear_all_realities(self) -> str:
        """
        Permanently delete all saved conversation realities.

        This removes only:
        - conversations
        - sessions

        It intentionally preserves:
        - long-term memories
        - command history

        A fresh empty session is created immediately so the
        assistant can continue working normally.
        """

        database = self.memory.database

        with database.lock:
            with database.connect() as connection:
                connection.execute(
                    "DELETE FROM conversations"
                )
                connection.execute(
                    "DELETE FROM sessions"
                )
                connection.commit()

        self.memory.session_id = (
            self.memory.create_session()
        )

        return self.memory.session_id

    def get_current_reality_id(self) -> str:
        return self.memory.session_id