from __future__ import annotations

import logging
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox

from core.app_paths import get_logs_dir


LOGGER_NAME = "mv.ai"


def configure_logging() -> Path:
    """
    Configure persistent file logging for MV.AI.

    Returns the current log file path.
    """
    logs_dir = get_logs_dir()
    log_path = logs_dir / "mv_ai.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)

    if not logger.handlers:
        handler = logging.FileHandler(
            log_path,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                "%(asctime)s | %(levelname)s | "
                "%(threadName)s | %(message)s"
            )
        )
        logger.addHandler(handler)

    return log_path


def _write_emergency_crash_file(
    exception_type,
    exception_value,
    exception_traceback,
) -> Path:
    """
    Write a separate crash report even if normal logging fails.
    """
    logs_dir = get_logs_dir()
    timestamp = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )
    crash_path = (
        logs_dir
        / f"crash_{timestamp}.log"
    )

    formatted = "".join(
        traceback.format_exception(
            exception_type,
            exception_value,
            exception_traceback,
        )
    )

    crash_path.write_text(
        formatted,
        encoding="utf-8",
    )

    return crash_path


def _show_crash_dialog(
    message: str,
    log_path: Path,
) -> None:
    """
    Show a user-friendly crash dialog when a QApplication exists.
    """
    app = QApplication.instance()

    if app is None:
        return

    QMessageBox.critical(
        None,
        "MV.AI encountered an error",
        (
            "MV.AI hit an unexpected error.\n\n"
            f"{message}\n\n"
            "A diagnostic log was saved here:\n"
            f"{log_path}"
        ),
    )


def handle_exception(
    exception_type,
    exception_value,
    exception_traceback,
) -> None:
    """
    Global handler for uncaught exceptions on the main thread.
    """
    if issubclass(
        exception_type,
        KeyboardInterrupt,
    ):
        sys.__excepthook__(
            exception_type,
            exception_value,
            exception_traceback,
        )
        return

    logger = logging.getLogger(LOGGER_NAME)

    try:
        logger.critical(
            "Uncaught exception",
            exc_info=(
                exception_type,
                exception_value,
                exception_traceback,
            ),
        )
    except Exception:
        pass

    try:
        log_path = _write_emergency_crash_file(
            exception_type,
            exception_value,
            exception_traceback,
        )
    except Exception:
        log_path = get_logs_dir()

    _show_crash_dialog(
        str(exception_value),
        log_path,
    )


def handle_thread_exception(args) -> None:
    """
    Global handler for uncaught exceptions in Python threads.
    """
    handle_exception(
        args.exc_type,
        args.exc_value,
        args.exc_traceback,
    )


def install_crash_handlers() -> Path:
    """
    Install logging and uncaught-exception handlers.
    """
    log_path = configure_logging()

    sys.excepthook = handle_exception

    if hasattr(threading, "excepthook"):
        threading.excepthook = (
            handle_thread_exception
        )

    logging.getLogger(LOGGER_NAME).info(
        "MV.AI crash handlers initialized."
    )

    return log_path