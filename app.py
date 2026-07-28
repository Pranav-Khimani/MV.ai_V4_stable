import logging
import sys

from PySide6.QtWidgets import QApplication

from core.app_paths import (
    ensure_app_directories,
    migrate_legacy_memory_database,
)
from core.crash_handler import install_crash_handlers
from core.database_backup import DatabaseBackupManager
from core.instance_manager import SingleInstanceManager
from ui.window import MVWindow


def main():
    """
    Start MV.AI with persistent AppData storage and crash logging.
    """
    ensure_app_directories()
    log_path = install_crash_handlers()

    logger = logging.getLogger("mv.ai")
    logger.info("Starting MV.AI.")
    logger.info("Log file: %s", log_path)

    app = QApplication(sys.argv)

    app.setApplicationName("MV.AI")
    app.setOrganizationName("MV.AI")

    instance_manager = SingleInstanceManager(
        parent=app
    )

    if not instance_manager.start():
        logger.info(
            "Secondary MV.AI process exiting."
        )
        return 0

    try:
        migrated = migrate_legacy_memory_database()

        if migrated:
            logger.info(
                "Migrated legacy memory database to AppData."
            )
    except Exception:
        # Migration failure must not silently destroy or overwrite data.
        logger.exception(
            "Legacy memory database migration failed."
        )

    backup_manager = DatabaseBackupManager()
    backup_manager.create_startup_backup_if_due()

    window = MVWindow()

    def activate_window():
        if window.isMinimized():
            window.showNormal()
        else:
            window.show()

        window.raise_()
        window.activateWindow()

    instance_manager.set_activation_callback(
        activate_window
    )
    app.aboutToQuit.connect(
        instance_manager.close
    )

    window.show()

    exit_code = app.exec()
    logger.info(
        "MV.AI exited with code %s.",
        exit_code,
    )

    sys.exit(exit_code)


if __name__ == "__main__":
    main()