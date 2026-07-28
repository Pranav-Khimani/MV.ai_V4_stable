from __future__ import annotations

import os
import shutil
from pathlib import Path


APP_FOLDER_NAME = "MV.ai"


def get_project_root() -> Path:
    """
    Return the source/project root.

    Used only for bundled read-only assets and one-time migration.
    """
    return Path(__file__).resolve().parent.parent


def get_app_data_dir() -> Path:
    """
    Return MV.AI's writable per-user application directory.

    Windows:
        %LOCALAPPDATA%\\MV.ai
    Fallback:
        ~/.mv.ai
    """
    local_app_data = os.getenv("LOCALAPPDATA")

    if local_app_data:
        root = Path(local_app_data) / APP_FOLDER_NAME
    else:
        root = Path.home() / ".mv.ai"

    root.mkdir(parents=True, exist_ok=True)
    return root


def get_data_dir() -> Path:
    path = get_app_data_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_logs_dir() -> Path:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_backups_dir() -> Path:
    path = get_app_data_dir() / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_cache_dir() -> Path:
    path = get_app_data_dir() / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_settings_path() -> Path:
    return get_app_data_dir() / "settings.json"


def get_memory_database_path() -> Path:
    return get_data_dir() / "mv_memory.db"


def ensure_app_directories() -> None:
    get_data_dir()
    get_logs_dir()
    get_backups_dir()
    get_cache_dir()


def migrate_legacy_memory_database() -> bool:
    """
    Copy the old project-local database into AppData once.

    Existing AppData memory is never overwritten.

    Returns True when a migration was performed.
    """
    destination = get_memory_database_path()

    if destination.exists():
        return False

    legacy = get_project_root() / "data" / "mv_memory.db"

    if not legacy.exists():
        return False

    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(legacy, destination)

    # SQLite WAL databases can have sidecar files. Copy them too
    # when present so the migration is as safe as possible.
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(legacy) + suffix)
        if sidecar.exists():
            shutil.copy2(
                sidecar,
                Path(str(destination) + suffix),
            )

    return True