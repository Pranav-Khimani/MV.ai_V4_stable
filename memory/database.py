import sqlite3
import threading
from pathlib import Path
from typing import Any


class MemoryDatabase:
    """
    Handles MV.AI's SQLite memory database.

    This class is responsible only for:
    - Creating the database
    - Creating tables
    - Running SQL queries
    - Managing database connections

    Higher-level memory behavior belongs in MemoryManager.
    """

    def __init__(
        self,
        database_path: str = "data/mv_memory.db",
    ):
        self.database_path = Path(database_path)
        self.lock = threading.RLock()

        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize_database()

    def connect(self) -> sqlite3.Connection:
        """
        Create and configure a SQLite connection.
        """

        connection = sqlite3.connect(
            self.database_path,
            timeout=10,
            check_same_thread=False,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA foreign_keys = ON"
        )

        connection.execute(
            "PRAGMA journal_mode = WAL"
        )

        return connection

    def initialize_database(self) -> None:
        """
        Create all memory tables if they do not exist.
        """

        with self.lock:
            with self.connect() as connection:
                connection.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        category TEXT NOT NULL DEFAULT 'general',
                        memory_key TEXT NOT NULL,
                        memory_value TEXT NOT NULL,
                        importance INTEGER NOT NULL DEFAULT 5,
                        source TEXT NOT NULL DEFAULT 'user',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_accessed_at TEXT,
                        access_count INTEGER NOT NULL DEFAULT 0,
                        is_active INTEGER NOT NULL DEFAULT 1,

                        UNIQUE(category, memory_key)
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_category
                    ON memories(category);

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_key
                    ON memories(memory_key);

                    CREATE INDEX IF NOT EXISTS
                    idx_memories_active
                    ON memories(is_active);

                    CREATE TABLE IF NOT EXISTS conversations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id TEXT NOT NULL,
                        role TEXT NOT NULL,
                        content TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_conversations_session
                    ON conversations(session_id);

                    CREATE INDEX IF NOT EXISTS
                    idx_conversations_created
                    ON conversations(created_at);

                    CREATE TABLE IF NOT EXISTS command_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        command TEXT NOT NULL,
                        success INTEGER NOT NULL DEFAULT 0,
                        response TEXT,
                        error TEXT,
                        created_at TEXT NOT NULL
                    );

                    CREATE INDEX IF NOT EXISTS
                    idx_command_history_created
                    ON command_history(created_at);

                    CREATE TABLE IF NOT EXISTS sessions (
                        id TEXT PRIMARY KEY,
                        started_at TEXT NOT NULL,
                        ended_at TEXT,
                        title TEXT,
                        message_count INTEGER NOT NULL DEFAULT 0
                    );
                    """
                )

                # Older MV.ai databases predate media attachments. Add the
                # column in-place so existing memories and Realities remain intact.
                columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(conversations)"
                    ).fetchall()
                }
                if "attachments_json" not in columns:
                    connection.execute(
                        "ALTER TABLE conversations "
                        "ADD COLUMN attachments_json TEXT NOT NULL DEFAULT '[]'"
                    )

                connection.commit()

    def execute(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> int:
        """
        Execute INSERT, UPDATE, or DELETE SQL.

        Returns the affected row ID where available.
        """

        with self.lock:
            with self.connect() as connection:
                cursor = connection.execute(
                    query,
                    parameters,
                )

                connection.commit()

                return cursor.lastrowid

    def execute_many(
        self,
        query: str,
        parameters: list[tuple[Any, ...]],
    ) -> None:
        """
        Execute one SQL query with multiple parameter sets.
        """

        with self.lock:
            with self.connect() as connection:
                connection.executemany(
                    query,
                    parameters,
                )

                connection.commit()

    def fetch_one(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> dict[str, Any] | None:
        """
        Fetch one database row as a dictionary.
        """

        with self.lock:
            with self.connect() as connection:
                cursor = connection.execute(
                    query,
                    parameters,
                )

                row = cursor.fetchone()

                if row is None:
                    return None

                return dict(row)

    def fetch_all(
        self,
        query: str,
        parameters: tuple[Any, ...] = (),
    ) -> list[dict[str, Any]]:
        """
        Fetch all matching rows as dictionaries.
        """

        with self.lock:
            with self.connect() as connection:
                cursor = connection.execute(
                    query,
                    parameters,
                )

                rows = cursor.fetchall()

                return [
                    dict(row)
                    for row in rows
                ]

    def close(self) -> None:
        """
        Included for API completeness.

        Connections are opened and closed per operation,
        so no persistent connection needs closing.
        """

        return