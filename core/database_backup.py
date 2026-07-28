from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from core.app_paths import (
    get_backups_dir,
    get_memory_database_path,
)


LOGGER = logging.getLogger("mv.ai")


class DatabaseBackupManager:
    """
    Create safe SQLite backups for MV.AI's memory database.

    SQLite's backup API is used instead of copying the database
    file directly, so backups remain consistent even when WAL mode
    is enabled.
    """

    BACKUP_PREFIX = "mv_memory_"
    BACKUP_SUFFIX = ".db"

    def __init__(
        self,
        database_path: str | Path | None = None,
        backups_dir: str | Path | None = None,
        keep_latest: int = 10,
    ):
        self.database_path = Path(
            database_path
            or get_memory_database_path()
        )
        self.backups_dir = Path(
            backups_dir
            or get_backups_dir()
        )
        self.keep_latest = max(
            3,
            int(keep_latest),
        )

        self.backups_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    @staticmethod
    def _safe_reason(
        reason: str,
    ) -> str:
        cleaned = re.sub(
            r"[^a-zA-Z0-9_-]+",
            "_",
            reason.strip(),
        ).strip("_")

        return cleaned[:40] or "automatic"

    def create_backup(
        self,
        reason: str = "automatic",
    ) -> Path | None:
        """
        Create and validate a backup.

        Returns its path, or None when there is no source database yet.
        """

        if (
            not self.database_path.exists()
            or self.database_path.stat().st_size == 0
        ):
            LOGGER.info(
                "Backup skipped because no memory database exists yet."
            )
            return None

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S_%f"
        )
        safe_reason = self._safe_reason(
            reason
        )

        destination = (
            self.backups_dir
            / (
                f"{self.BACKUP_PREFIX}"
                f"{timestamp}_{safe_reason}"
                f"{self.BACKUP_SUFFIX}"
            )
        )

        try:
            with sqlite3.connect(
                self.database_path,
                timeout=10,
                check_same_thread=False,
            ) as source:
                with sqlite3.connect(
                    destination,
                    timeout=10,
                ) as target:
                    source.backup(target)

            if not self._is_valid_database(
                destination
            ):
                destination.unlink(
                    missing_ok=True
                )
                raise RuntimeError(
                    "The created backup did not pass validation."
                )

            LOGGER.info(
                "Memory backup created: %s",
                destination,
            )

            self.prune_old_backups()
            return destination

        except Exception:
            LOGGER.exception(
                "Could not create memory backup."
            )
            destination.unlink(
                missing_ok=True
            )
            return None

    def create_startup_backup_if_due(
        self,
        minimum_hours: int = 24,
    ) -> Path | None:
        """
        Create at most one normal startup backup per time window.
        """

        latest = self.get_latest_backup()

        if latest is not None:
            modified = datetime.fromtimestamp(
                latest.stat().st_mtime
            )
            due_after = modified + timedelta(
                hours=max(1, minimum_hours)
            )

            if datetime.now() < due_after:
                LOGGER.info(
                    "Startup backup not due yet."
                )
                return None

        return self.create_backup(
            reason="startup"
        )

    def get_backups(self) -> list[Path]:
        return sorted(
            self.backups_dir.glob(
                f"{self.BACKUP_PREFIX}*"
                f"{self.BACKUP_SUFFIX}"
            ),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )

    def get_latest_backup(self) -> Path | None:
        backups = self.get_backups()
        return backups[0] if backups else None

    def prune_old_backups(self) -> None:
        backups = self.get_backups()

        for old_backup in backups[
            self.keep_latest:
        ]:
            try:
                old_backup.unlink()
                LOGGER.info(
                    "Removed old backup: %s",
                    old_backup,
                )
            except OSError:
                LOGGER.exception(
                    "Could not remove old backup: %s",
                    old_backup,
                )

    @staticmethod
    def _is_valid_database(
        database_path: Path,
    ) -> bool:
        try:
            with sqlite3.connect(
                database_path
            ) as connection:
                result = connection.execute(
                    "PRAGMA integrity_check"
                ).fetchone()

            return bool(
                result
                and result[0] == "ok"
            )

        except sqlite3.Error:
            return False
