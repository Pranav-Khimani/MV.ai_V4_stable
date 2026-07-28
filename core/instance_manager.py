from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject
from PySide6.QtNetwork import (
    QLocalServer,
    QLocalSocket,
)


LOGGER = logging.getLogger("mv.ai")


class SingleInstanceManager(QObject):
    """
    Prevent more than one MV.AI process from running.

    When a second copy launches, it sends an activation message
    to the existing process and then exits. The existing process
    can use that message to restore and focus its window.
    """

    ACTIVATION_MESSAGE = b"SHOW_MV_AI"

    def __init__(
        self,
        server_name: str = "MV.AI.SingleInstance",
        parent: QObject | None = None,
    ):
        super().__init__(parent)

        self.server_name = server_name
        self.server = QLocalServer(self)
        self.activation_callback: Callable[[], None] | None = None

        self.server.newConnection.connect(
            self._handle_new_connection
        )

    def start(self) -> bool:
        """
        Return True for the primary instance.

        Return False when another instance is already running.
        In that case, the existing instance is asked to show itself.
        """

        if self.server.listen(self.server_name):
            LOGGER.info(
                "Single-instance server started: %s",
                self.server_name,
            )
            return True

        if self._notify_existing_instance():
            LOGGER.info(
                "Existing MV.AI instance notified."
            )
            return False

        # A previous crash can leave a stale local-server record.
        # Remove it only after connection to a live process failed.
        QLocalServer.removeServer(
            self.server_name
        )

        if self.server.listen(self.server_name):
            LOGGER.warning(
                "Removed stale single-instance server record."
            )
            return True

        LOGGER.error(
            "Could not create single-instance server: %s",
            self.server.errorString(),
        )

        # Failing open is safer than making MV.AI impossible to launch.
        return True

    def set_activation_callback(
        self,
        callback: Callable[[], None],
    ) -> None:
        self.activation_callback = callback

    def _notify_existing_instance(self) -> bool:
        socket = QLocalSocket(self)
        socket.connectToServer(
            self.server_name
        )

        if not socket.waitForConnected(750):
            socket.abort()
            return False

        socket.write(
            self.ACTIVATION_MESSAGE
        )
        socket.flush()
        socket.waitForBytesWritten(750)
        socket.disconnectFromServer()

        return True

    def _handle_new_connection(self) -> None:
        while self.server.hasPendingConnections():
            socket = self.server.nextPendingConnection()

            if socket is None:
                continue

            socket.readyRead.connect(
                lambda current_socket=socket:
                self._read_message(current_socket)
            )

            # The small message may already be waiting by the time
            # the readyRead connection is installed.
            if socket.bytesAvailable() > 0:
                self._read_message(socket)

    def _read_message(
        self,
        socket: QLocalSocket,
    ) -> None:
        message = bytes(
            socket.readAll()
        )

        if (
            self.ACTIVATION_MESSAGE in message
            and self.activation_callback is not None
        ):
            LOGGER.info(
                "Activation request received."
            )
            self.activation_callback()

        socket.disconnectFromServer()
        socket.deleteLater()

    def close(self) -> None:
        if self.server.isListening():
            self.server.close()

        QLocalServer.removeServer(
            self.server_name
        )
