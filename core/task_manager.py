from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


LOGGER = logging.getLogger("mv.ai")


class TaskCancelledError(RuntimeError):
    """Raised when a cooperative MV.AI task is cancelled."""


class CancellationToken:
    """
    Thread-safe cooperative cancellation token.

    It cannot forcibly terminate Python or operating-system calls.
    Long operations stop at the next cancellation checkpoint.
    """

    def __init__(self):
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def raise_if_cancelled(self) -> None:
        if self.is_cancelled:
            raise TaskCancelledError(
                "Task cancelled by the user."
            )


class TaskSignals(QObject):
    started = Signal(str)
    progress = Signal(str, str, int, int, object)
    completed = Signal(str, object)
    failed = Signal(str, str)
    cancelled = Signal(str)


class TaskWorker(QRunnable):
    def __init__(
        self,
        task_id: str,
        function,
        cancellation_token: CancellationToken,
    ):
        super().__init__()
        self.task_id = task_id
        self.function = function
        self.cancellation_token = cancellation_token
        self.signals = TaskSignals()
        self.setAutoDelete(True)

    def emit_progress(
        self,
        stage: str,
        current: int = 0,
        total: int = 0,
        detail=None,
    ) -> None:
        self.signals.progress.emit(
            self.task_id,
            stage,
            current,
            total,
            detail,
        )

    def run(self) -> None:
        self.signals.started.emit(
            self.task_id
        )

        try:
            result = self.function(
                cancellation_token=self.cancellation_token,
                progress_callback=self.emit_progress,
            )
            self.cancellation_token.raise_if_cancelled()
            self.signals.completed.emit(
                self.task_id,
                result,
            )
        except TaskCancelledError:
            LOGGER.info(
                "Task cancelled: %s",
                self.task_id,
            )
            self.signals.cancelled.emit(
                self.task_id
            )
        except Exception as error:
            LOGGER.exception(
                "Background task failed: %s",
                self.task_id,
            )
            self.signals.failed.emit(
                self.task_id,
                str(error),
            )


@dataclass
class ActiveTask:
    worker: TaskWorker
    token: CancellationToken


class TaskManager(QObject):
    """
    Runs MV.AI work outside the Qt UI thread.

    The first version intentionally allows one foreground command
    at a time, matching the current MV.AI interaction model.
    """

    task_started = Signal(str)
    task_progress = Signal(str, str, int, int, object)
    task_completed = Signal(str, object)
    task_failed = Signal(str, str)
    task_cancelled = Signal(str)

    def __init__(
        self,
        parent: QObject | None = None,
        max_threads: int = 3,
    ):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(
            max(2, int(max_threads))
        )
        self._tasks: dict[str, ActiveTask] = {}

    def start(self, function) -> str:
        task_id = uuid.uuid4().hex
        token = CancellationToken()
        worker = TaskWorker(
            task_id=task_id,
            function=function,
            cancellation_token=token,
        )

        worker.signals.started.connect(
            self.task_started
        )
        worker.signals.progress.connect(
            self.task_progress
        )
        worker.signals.completed.connect(
            self._on_completed
        )
        worker.signals.failed.connect(
            self._on_failed
        )
        worker.signals.cancelled.connect(
            self._on_cancelled
        )

        self._tasks[task_id] = ActiveTask(
            worker=worker,
            token=token,
        )
        self.pool.start(worker)
        return task_id

    def cancel(self, task_id: str | None) -> bool:
        if not task_id:
            return False

        task = self._tasks.get(task_id)
        if task is None:
            return False

        task.token.cancel()
        return True

    def cancel_all(self) -> None:
        for task in tuple(
            self._tasks.values()
        ):
            task.token.cancel()

    def _on_completed(
        self,
        task_id: str,
        result,
    ) -> None:
        self._tasks.pop(task_id, None)
        self.task_completed.emit(
            task_id,
            result,
        )

    def _on_failed(
        self,
        task_id: str,
        message: str,
    ) -> None:
        self._tasks.pop(task_id, None)
        self.task_failed.emit(
            task_id,
            message,
        )

    def _on_cancelled(
        self,
        task_id: str,
    ) -> None:
        self._tasks.pop(task_id, None)
        self.task_cancelled.emit(
            task_id
        )