import random
import sys
import threading
from pathlib import Path

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QPropertyAnimation,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QFileDialog,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from core.assistant import Assistant
from core.error_formatting import merge_error_messages
from core.task_manager import TaskManager
from ui.widgets.image_attachment import ChatImageWidget, ImageAttachmentPreview
from ui.widgets.more_popup import MorePopup
from ui.widgets.reality_dock_button import RealityDockButton
from ui.widgets.recent_realities_popup import RecentRealitiesPopup
from voice.voice_assistant import VoiceAssistant


class UiBridge(QObject):
    """
    Safe bridge for sending data from background threads
    into the Qt user-interface thread.
    """

    report_ready = Signal(object)
    command_error = Signal(str)
    voice_status = Signal(str)
    voice_message = Signal(str)
    voice_command = Signal(str)
    progress = Signal(int, int, object)
    confirmation_requested = Signal(str, object, object, object)


class GlitchTextLabel(QLabel):
    """
    A QLabel that briefly distorts its text when the state changes.

    The effect is intentionally subtle:
    - only a few short frames
    - no flashing screen
    - no constant visual noise
    """

    GLITCH_CHARACTERS = "░▒▓<>/\\|_"

    def __init__(self, text="", parent=None):
        super().__init__(text, parent)

        self.final_text = text
        self.frames = []
        self.frame_index = 0

        self.glitch_timer = QTimer(self)
        self.glitch_timer.timeout.connect(
            self.show_next_frame
        )

    def glitch_to(
        self,
        text: str,
    ) -> None:
        """
        Glitch briefly, then settle on the requested text.
        """

        self.final_text = text
        self.frames = self.create_frames(text)
        self.frame_index = 0

        if self.glitch_timer.isActive():
            self.glitch_timer.stop()

        self.glitch_timer.start(110)

    def create_frames(
        self,
        text: str,
    ) -> list[str]:
        if not text:
            return [""]

        frames = []

        for _ in range(3):
            characters = list(text)
            change_count = max(
                1,
                len(characters) // 8,
            )

            for _ in range(change_count):
                index = random.randrange(
                    len(characters)
                )

                if characters[index] != " ":
                    characters[index] = random.choice(
                        self.GLITCH_CHARACTERS
                    )

            frames.append(
                "".join(characters)
            )

        frames.append(text)
        return frames

    def show_next_frame(self) -> None:
        if self.frame_index >= len(self.frames):
            self.glitch_timer.stop()
            self.setText(self.final_text)
            return

        self.setText(
            self.frames[self.frame_index]
        )

        self.frame_index += 1


class GlitchLoader(QFrame):
    """
    Minimal assistant-side signal loader.

    A small scan line moves across five signal cells. One cell
    occasionally splits for a subtle glitch, then the pattern
    reforms. The animation is intentionally calm.
    """

    FRAMES = (
        ("▰", "▪", "·", "·", "·"),
        ("▪", "▰", "▪", "·", "·"),
        ("·", "▪", "▰", "▪", "·"),
        ("·", "·", "▪", "▰", "▪"),
        ("·", "·", "·", "▪", "▰"),
        ("·", "·", "▪", "▰", "│"),
        ("·", "▪", "▰", "░", "·"),
        ("▪", "▰", "▪", "·", "·"),
    )

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setObjectName("glitchLoader")
        self.setStyleSheet(
            """
            QFrame#glitchLoader {
                background: #141823;
                border: 1px solid #2A3042;
                border-radius: 18px;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            14,
            9,
            14,
            9,
        )
        layout.setSpacing(5)

        self.prefix = QLabel("MV")
        self.prefix.setStyleSheet(
            """
            QLabel {
                color: #696F82;
                background: transparent;
                border: none;
                font-family: Consolas;
                font-size: 10px;
                font-weight: 600;
            }
            """
        )

        self.cells = []

        layout.addWidget(self.prefix)
        layout.addSpacing(4)

        for index in range(5):
            cell = QLabel(self.FRAMES[0][index])
            cell.setAlignment(
                Qt.AlignmentFlag.AlignCenter
            )
            cell.setFixedWidth(10)
            cell.setStyleSheet(
                """
                QLabel {
                    color: #8177FF;
                    background: transparent;
                    border: none;
                    font-family: Consolas;
                    font-size: 14px;
                }
                """
            )

            self.cells.append(cell)
            layout.addWidget(cell)

        self.frame_index = 0

        self.timer = QTimer(self)
        self.timer.timeout.connect(
            self.advance_frame
        )

        # Slower than the old loader so it reads as a calm
        # processing signal rather than rapid flickering.
        self.timer.start(175)

    def advance_frame(self) -> None:
        self.frame_index = (
            self.frame_index + 1
        ) % len(self.FRAMES)

        frame = self.FRAMES[
            self.frame_index
        ]

        for index, character in enumerate(frame):
            cell = self.cells[index]
            cell.setText(character)

            if character in {"▰", "│"}:
                color = "#A89FFF"
            elif character in {"▪", "░"}:
                color = "#8177FF"
            else:
                color = "#4C5264"

            cell.setStyleSheet(
                f"""
                QLabel {{
                    color: {color};
                    background: transparent;
                    border: none;
                    font-family: Consolas;
                    font-size: 14px;
                }}
                """
            )

        # Very short prefix glitch on two frames only.
        if self.frame_index == 5:
            self.prefix.setText("M/")
        elif self.frame_index == 6:
            self.prefix.setText("MV")
        else:
            self.prefix.setText("MV")

    def stop(self) -> None:
        self.timer.stop()


class MessageBubble(QFrame):
    """
    A minimal rounded chat bubble with no sender name.
    """

    def __init__(
        self,
        message: str,
        bubble_type: str = "assistant",
        image_path: str | None = None,
        parent=None,
    ):
        super().__init__(parent)

        colors = {
            "assistant": (
                "#171B27",
                "#2A3043",
                "#F5F7FB",
            ),
            "user": (
                "#2A3150",
                "#3C466C",
                "#F8F9FD",
            ),
            "error": (
                "#351F29",
                "#60303C",
                "#FF9AA5",
            ),
            "step": (
                "#141823",
                "#282E40",
                "#A0A7B8",
            ),
        }

        background, border, text_color = colors.get(
            bubble_type,
            colors["assistant"],
        )

        self.setObjectName("messageBubble")
        self.setStyleSheet(
            f"""
            QFrame#messageBubble {{
                background: {background};
                border: 1px solid {border};
                border-radius: 20px;
            }}
            """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 13, 18, 13)

        if image_path:
            layout.addWidget(ChatImageWidget(image_path))

        self.message_label = QLabel(message)
        self.message_label.setWordWrap(True)
        self.message_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )
        self.message_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self.message_label.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
                background: transparent;
                border: none;
                font-size: 14px;
            }}
            """
        )

        layout.addWidget(self.message_label)


class MVWindow(QMainWindow):
    """
    PySide6 interface for MV.AI.

    The backend, memory, voice system, tools, and Spark
    workflows remain unchanged. This file replaces only
    the visual interface.
    """

    BG = "#07090E"
    PANEL = "#10131C"
    PANEL_ALT = "#151927"
    BORDER = "#2A3042"

    TEXT = "#F5F7FB"
    MUTED = "#9299AA"

    ACCENT = "#7A6CFF"
    ACCENT_HOVER = "#6658ED"

    SUCCESS = "#6EE7A0"
    WARNING = "#F5C96A"
    ERROR = "#FF7A89"
    INFO = "#6FA7FF"

    PLACEHOLDER = "> System initialized, awaiting orders..."

    def __init__(self):
        super().__init__()

        self.assistant = Assistant()
        self.task_manager = TaskManager(
            parent=self,
            max_threads=3,
        )
        self.active_task_id = None
        self.voice_assistant = None

        self.is_working = False
        self.voice_enabled = False
        self.chat_started = False

        # UI-only animation state.
        self.thinking_row = None
        self.thinking_loader = None
        self.active_animations = []
        self.message_bubbles: list[MessageBubble] = []
        self.pending_image_path: str | None = None
        self.pending_image_details: dict | None = None

        # Only one Recent Realities panel may exist.
        self.recent_realities_popup = None
        self.more_popup = None

        self.bridge = UiBridge()
        self.connect_bridge()

        self.setup_window()
        self.build_ui()
        self.setup_task_manager()
        self.setup_desktop_notifications()
        self.show_welcome_screen()
        QTimer.singleShot(250, self.show_plugin_warnings)

        self.start_voice_timer()

    # --------------------------------------------------
    # Setup
    # --------------------------------------------------

    def setup_window(self):
        self.setWindowTitle("MV.AI")
        self.resize(1180, 780)
        self.setMinimumSize(840, 600)

        icon_path = self.find_logo_path()

        if icon_path:
            self.setWindowIcon(
                QIcon(str(icon_path))
            )

        self.setStyleSheet(
            f"""
            QMainWindow {{
                background: {self.BG};
            }}

            QWidget {{
                font-family: "Segoe UI";
            }}

            QScrollBar:vertical {{
                background: transparent;
                width: 8px;
                margin: 2px;
            }}

            QScrollBar::handle:vertical {{
                background: #20263A;
                min-height: 34px;
                border-radius: 4px;
            }}

            QScrollBar::handle:vertical:hover {{
                background: #303952;
            }}

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            """
        )

    def connect_bridge(self):
        self.bridge.report_ready.connect(
            self.display_report
        )
        self.bridge.command_error.connect(
            self.display_command_error
        )
        self.bridge.voice_status.connect(
            self.apply_voice_status
        )
        self.bridge.voice_message.connect(
            self.show_voice_message
        )
        self.bridge.voice_command.connect(
            self.handle_voice_command
        )
        self.bridge.progress.connect(
            self.show_progress
        )
        self.bridge.confirmation_requested.connect(
            self.handle_confirmation_request
        )

    def setup_task_manager(self) -> None:
        self.task_manager.task_progress.connect(
            self.handle_task_progress
        )
        self.task_manager.task_completed.connect(
            self.handle_task_completed
        )
        self.task_manager.task_failed.connect(
            self.handle_task_failed
        )
        self.task_manager.task_cancelled.connect(
            self.handle_task_cancelled
        )

    def setup_desktop_notifications(self) -> None:
        self.notification_tray = QSystemTrayIcon(
            self.windowIcon(),
            self,
        )
        self.notification_tray.setToolTip(
            "MV.AI"
        )
        self.notification_tray.messageClicked.connect(
            self.show_and_focus
        )
        self.notification_tray.show()

    def show_and_focus(self) -> None:
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()

        self.raise_()
        self.activateWindow()

    def notify_desktop(
        self,
        title: str,
        message: str,
        icon=QSystemTrayIcon.MessageIcon.Information,
    ) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        self.notification_tray.showMessage(
            title,
            message,
            icon,
            5000,
        )

    def build_ui(self):
        central = QWidget()
        central.setObjectName("central")
        central.setStyleSheet(
            f"""
            QWidget#central {{
                background: {self.BG};
            }}
            """
        )
        self.setCentralWidget(central)

        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(30, 20, 28, 26)
        root_layout.setSpacing(12)

        root_layout.addWidget(
            self.create_header()
        )

        self.main_panel = QFrame()
        self.main_panel.setObjectName("mainPanel")
        self.main_panel.setStyleSheet(
            f"""
            QFrame#mainPanel {{
                background: {self.PANEL};
                border: 1px solid {self.BORDER};
                border-radius: 28px;
            }}
            """
        )

        panel_layout = QVBoxLayout(self.main_panel)
        panel_layout.setContentsMargins(24, 22, 24, 18)
        panel_layout.setSpacing(14)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(
            QFrame.Shape.NoFrame
        )
        self.scroll_area.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
        )

        self.chat_container = QWidget()
        self.chat_container.setStyleSheet(
            "background: transparent;"
        )

        self.chat_layout = QVBoxLayout(
            self.chat_container
        )
        self.chat_layout.setContentsMargins(
            12,
            6,
            12,
            12,
        )
        self.chat_layout.setSpacing(12)
        self.chat_layout.addStretch(1)

        self.scroll_area.setWidget(
            self.chat_container
        )

        panel_layout.addWidget(
            self.scroll_area,
            1,
        )
        panel_layout.addWidget(
            self.create_input_bar()
        )

        root_layout.addWidget(
            self.main_panel,
            1,
        )

    # --------------------------------------------------
    # Header
    # --------------------------------------------------

    def create_header(self):
        header = QFrame()
        header.setStyleSheet(
            "background: transparent;"
        )
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(4, 0, 4, 0)
        header_layout.setSpacing(12)

        brand = QLabel("MV.AI")
        brand.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT};
                font-size: 22px;
                font-weight: 700;
            }}
            """
        )

        header_layout.addWidget(
            brand
        )

        self.new_reality_button = RealityDockButton(
            icon_text="⊕",
            label_text="New Reality",
        )
        self.new_reality_button.activated.connect(
            self.start_new_reality
        )

        self.recent_realities_button = RealityDockButton(
            icon_text="◷",
            label_text="Recent Realities",
            expanded_width=190,
        )
        self.recent_realities_button.activated.connect(
            self.show_recent_realities
        )

        self.sparks_button = RealityDockButton(
            icon_text="⚡",
            label_text="Sparks",
            expanded_width=125,
        )
        self.sparks_button.activated.connect(
            self.open_sparks
        )

        self.more_button = RealityDockButton(
            icon_text="•••",
            label_text="More",
            expanded_width=118,
        )
        self.more_button.activated.connect(
            self.toggle_more_popup
        )

        header_layout.addWidget(
            self.new_reality_button
        )
        header_layout.addWidget(
            self.recent_realities_button
        )
        header_layout.addWidget(
            self.sparks_button
        )
        header_layout.addWidget(
            self.more_button
        )
        header_layout.addStretch(1)

        self.status_frame = QFrame()
        self.status_frame.setObjectName("statusFrame")
        self.status_frame.setStyleSheet(
            f"""
            QFrame#statusFrame {{
                background: {self.PANEL_ALT};
                border: 1px solid {self.BORDER};
                border-radius: 22px;
            }}
            """
        )

        status_layout = QHBoxLayout(
            self.status_frame
        )
        status_layout.setContentsMargins(
            14,
            8,
            14,
            8,
        )
        status_layout.setSpacing(7)

        self.status_dot = QLabel("●")
        self.status_dot.setStyleSheet(
            f"color: {self.SUCCESS}; font-size: 11px;"
        )

        self.status_label = GlitchTextLabel("Ready")
        self.status_label.setStyleSheet(
            f"color: {self.TEXT}; font-size: 12px;"
        )

        status_layout.addWidget(
            self.status_dot
        )
        status_layout.addWidget(
            self.status_label
        )

        header_layout.addWidget(
            self.status_frame
        )

        return header

    # --------------------------------------------------
    # Welcome screen
    # --------------------------------------------------

    def show_welcome_screen(self):
        self.welcome_widget = QWidget()
        self.welcome_widget.setStyleSheet(
            "background: transparent;"
        )

        layout = QVBoxLayout(
            self.welcome_widget
        )
        layout.setContentsMargins(
            30,
            75,
            30,
            55,
        )
        layout.setSpacing(0)
        layout.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.welcome_logo = QLabel()
        self.welcome_logo.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.welcome_logo.setFixedSize(
            130,
            130,
        )

        logo = self.load_logo_pixmap(
            QSize(116, 116)
        )

        if logo:
            self.welcome_logo.setPixmap(logo)
        else:
            self.welcome_logo.setText("▲")
            self.welcome_logo.setStyleSheet(
                f"""
                QLabel {{
                    color: {self.TEXT};
                    font-size: 70px;
                }}
                """
            )

        title = QLabel("Hey, Pranav!")
        title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        title.setStyleSheet(
            f"""
            QLabel {{
                color: {self.TEXT};
                font-size: 40px;
                font-weight: 700;
                background: transparent;
            }}
            """
        )

        subtitle = QLabel(
            "What’s tingling your brain today?"
        )
        subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        subtitle.setStyleSheet(
            f"""
            QLabel {{
                color: {self.MUTED};
                font-size: 18px;
                background: transparent;
            }}
            """
        )

        button = QPushButton(
            "✦  Let’s create a new reality!"
        )
        button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        button.setFixedSize(
            320,
            54,
        )
        button.clicked.connect(
            self.focus_input
        )
        button.setStyleSheet(
            f"""
            QPushButton {{
                background: {self.PANEL_ALT};
                color: {self.TEXT};
                border: 1px solid {self.ACCENT};
                border-radius: 27px;
                font-size: 15px;
                font-weight: 600;
            }}

            QPushButton:hover {{
                background: #1B2030;
            }}
            """
        )

        layout.addWidget(
            self.welcome_logo,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )
        layout.addSpacing(18)
        layout.addWidget(title)
        layout.addSpacing(10)
        layout.addWidget(subtitle)
        layout.addSpacing(28)
        layout.addWidget(
            button,
            alignment=Qt.AlignmentFlag.AlignCenter,
        )

        self.chat_layout.insertWidget(
            0,
            self.welcome_widget,
            1,
        )

    def hide_welcome_screen(self):
        if self.chat_started:
            return

        self.chat_started = True

        if hasattr(self, "welcome_widget"):
            self.chat_layout.removeWidget(
                self.welcome_widget
            )
            self.welcome_widget.deleteLater()

    def show_recent_realities(self) -> None:
        """
        Load saved realities from SQLite and open the popup.
        """

        if self.is_working:
            self.set_status(
                "WAIT//TASK ACTIVE",
                self.WARNING,
            )
            return

        try:
            realities = (
                self.assistant
                .get_recent_realities(
                    limit=30
                )
            )
        except Exception as error:
            self.add_message(
                f"Could not load recent realities: {error}",
                "error",
            )
            return

        # Toggle the current popup instead of stacking copies.
        if (
            self.recent_realities_popup is not None
            and self.recent_realities_popup.isVisible()
        ):
            self.recent_realities_popup.close()
            self.recent_realities_popup = None
            return

        popup = RecentRealitiesPopup(
            realities=realities,
            parent=self,
        )
        self.recent_realities_popup = popup

        popup.reality_selected.connect(
            self.load_selected_reality
        )
        popup.clear_requested.connect(
            lambda: self.confirm_clear_all_realities(
                popup
            )
        )
        popup.finished.connect(
            self.cleanup_recent_realities_popup
        )
        popup.destroyed.connect(
            self.cleanup_recent_realities_popup
        )

        button_position = (
            self.recent_realities_button
            .mapToGlobal(
                self.recent_realities_button
                .rect()
                .bottomLeft()
            )
        )

        popup.move(
            button_position.x(),
            button_position.y() + 9,
        )
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def cleanup_recent_realities_popup(
        self,
        *args,
    ) -> None:
        """Forget the popup after it closes."""

        self.recent_realities_popup = None

    def toggle_more_popup(self) -> None:
        if (
            self.more_popup is not None
            and self.more_popup.isVisible()
        ):
            self.more_popup.close()
            self.more_popup = None
            return

        # Close Recent Realities safely without depending on a method
        # that does not exist in this version of MVWindow.
        if self.recent_realities_popup is not None:
            self.recent_realities_popup.close()
            self.recent_realities_popup = None

        popup = MorePopup(
            parent=self,
            memory_manager=self.assistant.memory,
        )
        self.more_popup = popup

        popup.finished.connect(
            self.cleanup_more_popup
        )
        popup.destroyed.connect(
            self.cleanup_more_popup
        )

        position = self.more_button.mapToGlobal(
            self.more_button.rect().bottomLeft()
        )

        screen = self.screen().availableGeometry()
        x = min(
            position.x(),
            screen.right() - popup.width() - 12,
        )
        y = min(
            position.y() + 9,
            screen.bottom() - popup.height() - 12,
        )

        popup.move(
            max(screen.left() + 12, x),
            max(screen.top() + 12, y),
        )
        popup.show()
        popup.raise_()
        popup.activateWindow()

    def cleanup_more_popup(
        self,
        *args,
    ) -> None:
        self.more_popup = None

    def confirm_clear_all_realities(
        self,
        popup=None,
    ) -> None:
        """
        Ask for confirmation, then permanently clear saved
        realities while preserving long-term memories.
        """

        answer = QMessageBox.question(
            self,
            "Clear Recent Realities",
            (
                "Clear every saved reality?\n\n"
                "This permanently removes all saved "
                "conversation history.\n"
                "Your long-term memories and command history "
                "will not be deleted."
            ),
            (
                QMessageBox.StandardButton.Yes
                | QMessageBox.StandardButton.Cancel
            ),
            QMessageBox.StandardButton.Cancel,
        )

        if (
            answer
            != QMessageBox.StandardButton.Yes
        ):
            return

        try:
            self.assistant.clear_all_realities()
        except Exception as error:
            QMessageBox.critical(
                self,
                "Could Not Clear Realities",
                str(error),
            )
            return

        if popup is not None:
            popup.accept()

        self.clear_visible_reality()
        self.clear_pending_image()
        self.chat_started = False
        self.command_entry.clear()
        self.show_welcome_screen()
        self.scroll_to_bottom()
        self.command_entry.setFocus()

        self.set_status(
            "REALITIES//CLEARED",
            self.SUCCESS,
        )

    def clear_visible_reality(self) -> None:
        """
        Remove visible chat widgets while preserving the
        permanent stretch at the bottom of the layout.
        """

        self.hide_thinking_loader()
        self.message_bubbles.clear()

        for index in range(
            self.chat_layout.count() - 2,
            -1,
            -1,
        ):
            item = self.chat_layout.itemAt(index)
            widget = item.widget()

            if widget is not None:
                self.chat_layout.removeWidget(widget)
                widget.deleteLater()

    def load_selected_reality(
        self,
        session_id: str,
    ) -> None:
        """
        Restore one saved reality into the chat interface.
        """

        if self.is_working:
            self.set_status(
                "WAIT//TASK ACTIVE",
                self.WARNING,
            )
            return

        try:
            messages = (
                self.assistant
                .load_reality(
                    session_id
                )
            )
        except Exception as error:
            self.add_message(
                f"Could not open that reality: {error}",
                "error",
            )
            return

        self.clear_visible_reality()
        self.clear_pending_image()
        self.command_entry.clear()

        if not messages:
            self.chat_started = False
            self.show_welcome_screen()
            return

        self.chat_started = True

        for message in messages:
            role = (
                message.get("role")
                or "assistant"
            ).lower()

            content = (
                message.get("content")
                or ""
            ).strip()
            attachments = message.get("attachments") or []
            image_path = None
            for attachment in attachments:
                if attachment.get("kind") != "image":
                    continue
                resolved = self.assistant.media_store.resolve_path(attachment)
                if resolved is not None:
                    image_path = str(resolved)
                    break

            if not content and image_path is None:
                continue

            bubble_type = (
                "user"
                if role == "user"
                else "assistant"
            )

            self.add_message(
                content,
                bubble_type,
                image_path=image_path,
            )

        self.scroll_to_bottom()
        self.command_entry.setFocus()
        self.set_status(
            "REALITY//RESTORED",
            self.INFO,
        )

    def open_sparks(self) -> None:
        """
        Prepare the command box for a Spark workflow.
        """

        if self.is_working:
            self.set_status(
                "WAIT//TASK ACTIVE",
                self.WARNING,
            )
            return

        self.command_entry.setText(
            "spark "
        )
        self.command_entry.setFocus()
        self.command_entry.setCursorPosition(
            len(self.command_entry.text())
        )

        self.set_status(
            "SPARKS//READY",
            self.ACCENT,
        )

    def start_new_reality(self) -> None:
        """
        Save the current reality, create a fresh database
        session, clear the UI, and restore the welcome screen.
        """

        if self.is_working:
            self.set_status(
                "WAIT//TASK ACTIVE",
                self.WARNING,
            )
            return

        try:
            self.assistant.start_new_reality()
        except Exception as error:
            self.add_message(
                f"Could not create a new reality: {error}",
                "error",
            )
            return

        self.clear_visible_reality()
        self.clear_pending_image()

        self.chat_started = False
        self.command_entry.clear()

        self.show_welcome_screen()
        self.scroll_to_bottom()
        self.command_entry.setFocus()

        if self.voice_enabled:
            self.set_status(
                "LISTENING//HEY MV",
                self.SUCCESS,
            )
        else:
            self.set_status(
                "MIC//OFF",
                self.MUTED,
            )

    # --------------------------------------------------
    # Input bar
    # --------------------------------------------------

    def create_input_bar(self):
        wrapper = QFrame()
        wrapper.setObjectName("inputWrapper")
        wrapper.setStyleSheet(
            f"""
            QFrame#inputWrapper {{
                background: {self.PANEL_ALT};
                border: 1px solid {self.BORDER};
                border-radius: 30px;
            }}
            """
        )

        outer_layout = QVBoxLayout(wrapper)
        outer_layout.setContentsMargins(12, 8, 9, 8)
        outer_layout.setSpacing(7)

        self.image_attachment_preview = ImageAttachmentPreview()
        self.image_attachment_preview.remove_requested.connect(
            self.clear_pending_image
        )
        outer_layout.addWidget(self.image_attachment_preview)

        input_row = QFrame()
        input_row.setStyleSheet("background: transparent; border: none;")
        layout = QHBoxLayout(input_row)
        layout.setContentsMargins(2, 0, 0, 0)
        layout.setSpacing(7)

        self.add_stuff_popup = None

        self.add_stuff_button = QPushButton("+")
        self.add_stuff_button.setObjectName("addStuffButton")
        self.add_stuff_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_stuff_button.setFixedSize(46, 46)
        self.add_stuff_button.setToolTip("Add stuff")
        self.add_stuff_button.clicked.connect(self.toggle_add_stuff_popup)
        self.add_stuff_button.setStyleSheet(
            f"""
            QPushButton#addStuffButton {{
                background: #1B2030;
                color: {self.TEXT};
                border: 1px solid #30374C;
                border-radius: 23px;
                font-size: 25px;
                font-weight: 400;
                padding-bottom: 3px;
            }}
            QPushButton#addStuffButton:hover {{
                background: #252C40;
                border-color: {self.ACCENT};
            }}
            QPushButton#addStuffButton:pressed {{
                background: #2B3248;
            }}
            QPushButton#addStuffButton:disabled {{
                background: #171A24;
                color: #686D7B;
                border-color: #252936;
            }}
            """
        )

        self.command_entry = QLineEdit()
        self.command_entry.setPlaceholderText(self.PLACEHOLDER)
        self.command_entry.setMinimumHeight(48)
        self.command_entry.returnPressed.connect(self.send_command)
        self.command_entry.setStyleSheet(
            f"""
            QLineEdit {{
                background: transparent;
                color: {self.TEXT};
                border: none;
                padding: 0px 4px;
                font-size: 15px;
                selection-background-color: {self.ACCENT};
            }}
            QLineEdit::placeholder {{ color: {self.MUTED}; }}
            """
        )

        self.microphone_button = QPushButton("🎙")
        self.microphone_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.microphone_button.setFixedSize(48, 48)
        self.microphone_button.clicked.connect(self.microphone_clicked)
        self.microphone_button.setStyleSheet(
            f"""
            QPushButton {{
                background: #1B2030;
                color: {self.TEXT};
                border: none;
                border-radius: 24px;
                font-size: 18px;
            }}
            QPushButton:hover {{ background: #252C40; }}
            """
        )

        self.send_button = QPushButton("➤")
        self.send_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.send_button.setFixedSize(48, 48)
        self.send_button.clicked.connect(self.send_or_cancel)
        self.send_button.setStyleSheet(
            f"""
            QPushButton {{
                background: {self.ACCENT};
                color: white;
                border: none;
                border-radius: 24px;
                font-size: 19px;
                font-weight: 700;
            }}
            QPushButton:hover {{ background: {self.ACCENT_HOVER}; }}
            QPushButton:disabled {{
                background: #343643;
                color: #989BA7;
            }}
            """
        )

        layout.addWidget(self.add_stuff_button)
        layout.addWidget(self.command_entry, 1)
        layout.addWidget(self.microphone_button)
        layout.addWidget(self.send_button)
        outer_layout.addWidget(input_row)
        return wrapper

    def toggle_add_stuff_popup(self) -> None:
        """Open or close the compact ADD Stuff menu."""

        if self.is_working:
            self.set_status("WAIT//TASK ACTIVE", self.WARNING)
            return

        if self.add_stuff_popup is not None and self.add_stuff_popup.isVisible():
            self.close_add_stuff_popup()
            return

        self.show_add_stuff_popup()

    def show_add_stuff_popup(self) -> None:
        """Show a small action popup directly above the + button."""

        self.close_add_stuff_popup()

        popup = QFrame()
        popup.setObjectName("addStuffPopup")
        popup.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
        )

        # A translucent top-level frame can cause Qt to paint only the
        # child text, making the menu look like it has no background.
        # Force stylesheet-backed, opaque painting for the popup panel.
        popup.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        popup.setAutoFillBackground(True)
        popup.setFixedSize(196, 64)
        popup.setStyleSheet(
            f"""
            QFrame#addStuffPopup {{
                background-color: #171C29;
                border: 1px solid #343C53;
                border-radius: 16px;
            }}
            QPushButton#addFilesAction {{
                background-color: #1D2332;
                color: {self.TEXT};
                border: 1px solid #2D354A;
                border-radius: 11px;
                padding: 0 14px;
                text-align: left;
                font-size: 14px;
                font-weight: 600;
            }}
            QPushButton#addFilesAction:hover {{
                background-color: #282F43;
                border-color: {self.ACCENT};
            }}
            QPushButton#addFilesAction:pressed {{
                background-color: #30384E;
            }}
            """
        )

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(8, 8, 8, 8)
        popup_layout.setSpacing(0)

        add_files_button = QPushButton("＋   Add files")
        add_files_button.setObjectName("addFilesAction")
        add_files_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_files_button.setFixedHeight(46)
        add_files_button.clicked.connect(self.choose_files_from_popup)
        popup_layout.addWidget(add_files_button)

        popup.adjustSize()
        anchor = self.add_stuff_button.mapToGlobal(
            self.add_stuff_button.rect().topLeft()
        )
        popup.move(
            anchor.x(),
            max(8, anchor.y() - popup.height() - 10),
        )

        self.add_stuff_popup = popup
        popup.destroyed.connect(self.on_add_stuff_popup_destroyed)
        popup.show()
        popup.raise_()
        add_files_button.setFocus()

    def choose_files_from_popup(self) -> None:
        """Close the action popup, then open the image file picker."""

        self.close_add_stuff_popup()
        QTimer.singleShot(0, self.choose_stuff)

    def close_add_stuff_popup(self) -> None:
        popup = self.add_stuff_popup
        self.add_stuff_popup = None
        if popup is not None:
            popup.close()
            popup.deleteLater()

    def on_add_stuff_popup_destroyed(self, *_args) -> None:
        self.add_stuff_popup = None

    def choose_stuff(self) -> None:
        """Choose one image and stage it for the next message."""

        if self.is_working:
            self.set_status("WAIT//TASK ACTIVE", self.WARNING)
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Add stuff to MV.ai",
            str(Path.home()),
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not file_path:
            return

        try:
            details = self.assistant.media_store.inspect_image(file_path)
            self.image_attachment_preview.set_image(
                details["path"],
                details["size_bytes"],
            )
        except Exception as error:
            QMessageBox.warning(self, "Could not add image", str(error))
            self.clear_pending_image()
            return

        self.pending_image_path = str(details["path"])
        self.pending_image_details = details
        self.command_entry.setPlaceholderText(
            "Ask MV.ai anything about this image..."
        )
        self.command_entry.setFocus()
        self.set_status("IMAGE//READY", self.ACCENT)

    def clear_pending_image(self) -> None:
        self.pending_image_path = None
        self.pending_image_details = None
        if hasattr(self, "image_attachment_preview"):
            self.image_attachment_preview.clear()
        if hasattr(self, "command_entry"):
            self.command_entry.setPlaceholderText(self.PLACEHOLDER)
        if not self.is_working and hasattr(self, "status_label"):
            if self.voice_enabled:
                self.set_status("LISTENING//HEY MV", self.SUCCESS)
            else:
                self.set_status("MIC//OFF", self.MUTED)

    # --------------------------------------------------
    # Logo
    # --------------------------------------------------

    def find_logo_path(self):
        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
        )

        assets = project_root / "assets"

        candidates = [
            assets / "mv_logo.png",
            assets / "mv_logo.jpg",
            assets / "mv_logo.jpeg",
            assets / "MV.ai logo.jpg",
        ]

        for path in candidates:
            if path.exists():
                return path

        if assets.exists():
            for path in assets.iterdir():
                if (
                    path.is_file()
                    and "mv_logo" in path.name.lower()
                    and path.suffix.lower()
                    in {
                        ".png",
                        ".jpg",
                        ".jpeg",
                        ".webp",
                    }
                ):
                    return path

        return None

    def load_logo_pixmap(
        self,
        target_size: QSize,
    ):
        path = self.find_logo_path()

        if path is None:
            print(
                "[UI] Logo not found in assets."
            )
            return None

        pixmap = QPixmap(str(path))

        if pixmap.isNull():
            print(
                f"[UI] Could not load logo: {path}"
            )
            return None

        # Qt preserves the original image without inventing
        # an alpha mask or changing its colors.
        return pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )

    # --------------------------------------------------
    # Chat
    # --------------------------------------------------

    def add_message(
        self,
        message: str,
        message_type: str = "assistant",
        image_path: str | None = None,
    ):
        self.hide_welcome_screen()

        row = QWidget()
        row.setStyleSheet(
            "background: transparent;"
        )

        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(
            4,
            0,
            4,
            0,
        )

        bubble = MessageBubble(
            message=message,
            bubble_type=message_type,
            image_path=image_path,
        )
        bubble.setFixedWidth(
            self.calculate_message_bubble_width()
        )
        bubble.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Minimum,
        )
        self.message_bubbles.append(bubble)

        if message_type == "user":
            row_layout.addStretch(1)
            row_layout.addWidget(bubble)
        else:
            row_layout.addWidget(bubble)
            row_layout.addStretch(1)

        # Insert before the permanent bottom stretch.
        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1,
            row,
        )

        self.animate_widget_in(row)
        self.scroll_to_bottom()

    def calculate_message_bubble_width(self) -> int:
        """Return a readable responsive width for all chat bubbles."""

        viewport_width = 0
        if hasattr(self, "scroll_area"):
            viewport_width = self.scroll_area.viewport().width()

        if viewport_width <= 0:
            viewport_width = self.width() - 120

        return max(420, min(760, int(viewport_width * 0.48)))

    def update_message_bubble_widths(self) -> None:
        """Resize existing bubbles when the main window changes size."""

        target_width = self.calculate_message_bubble_width()
        live_bubbles = []

        for bubble in self.message_bubbles:
            try:
                bubble.setFixedWidth(target_width)
                live_bubbles.append(bubble)
            except RuntimeError:
                # The Qt object was already deleted with an old Reality.
                continue

        self.message_bubbles = live_bubbles

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_message_bubble_widths()

    def animate_widget_in(
        self,
        widget: QWidget,
    ) -> None:
        """
        Fade a new chat item in without changing its layout.
        """

        effect = QGraphicsOpacityEffect(
            widget
        )
        widget.setGraphicsEffect(effect)
        effect.setOpacity(0.0)

        animation = QPropertyAnimation(
            effect,
            b"opacity",
            self,
        )
        animation.setDuration(180)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self.keep_animation(animation)
        animation.start()

    def show_thinking_loader(self) -> None:
        """
        Show the temporary glitch loader on the assistant side.
        """

        if self.thinking_row is not None:
            return

        self.hide_welcome_screen()

        self.thinking_row = QWidget()
        self.thinking_row.setStyleSheet(
            "background: transparent;"
        )

        row_layout = QHBoxLayout(
            self.thinking_row
        )
        row_layout.setContentsMargins(
            4,
            0,
            4,
            0,
        )

        self.thinking_loader = (
            GlitchLoader()
        )

        row_layout.addWidget(
            self.thinking_loader
        )
        row_layout.addStretch(1)

        self.chat_layout.insertWidget(
            self.chat_layout.count() - 1,
            self.thinking_row,
        )

        self.animate_widget_in(
            self.thinking_row
        )
        self.scroll_to_bottom()

    def hide_thinking_loader(self) -> None:
        """
        Remove the temporary loader before showing a response.
        """

        if self.thinking_row is None:
            return

        if self.thinking_loader is not None:
            self.thinking_loader.stop()

        row = self.thinking_row

        self.thinking_row = None
        self.thinking_loader = None

        effect = QGraphicsOpacityEffect(
            row
        )
        row.setGraphicsEffect(effect)

        animation = QPropertyAnimation(
            effect,
            b"opacity",
            self,
        )
        animation.setDuration(110)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)

        def remove_row():
            self.chat_layout.removeWidget(
                row
            )
            row.deleteLater()

        animation.finished.connect(
            remove_row
        )

        self.keep_animation(animation)
        animation.start()

    def keep_animation(
        self,
        animation,
    ) -> None:
        """
        Keep Qt animations alive until they finish.
        """

        self.active_animations.append(
            animation
        )

        def cleanup():
            if animation in self.active_animations:
                self.active_animations.remove(
                    animation
                )

        animation.finished.connect(
            cleanup
        )

    def scroll_to_bottom(self):
        def move():
            bar = self.scroll_area.verticalScrollBar()
            bar.setValue(
                bar.maximum()
            )

        QApplication.instance().processEvents()
        self.bridge.voice_message.emit(
            "__scroll__"
        )

        from PySide6.QtCore import QTimer
        QTimer.singleShot(
            60,
            move,
        )

    # --------------------------------------------------
    # Commands
    # --------------------------------------------------

    def focus_input(self):
        self.command_entry.setFocus()

    def send_or_cancel(self) -> None:
        if self.is_working:
            self.cancel_active_task()
        else:
            self.send_command()

    def send_command(self):
        if self.is_working:
            return

        command = self.command_entry.text().strip()
        has_image = bool(self.pending_image_path)

        if not command and not has_image:
            return
        if not command:
            command = "Describe this image and point out its most important details."

        attachment = None
        if has_image:
            try:
                attachment = self.assistant.import_image_attachment(
                    self.pending_image_path
                )
            except Exception as error:
                QMessageBox.warning(self, "Could not add image", str(error))
                return

        self.command_entry.clear()

        if attachment is not None:
            self.add_message(
                command,
                "user",
                image_path=attachment.get("path"),
            )
            self.clear_pending_image()
        else:
            self.add_message(command, "user")

        self.start_command_task(command, attachment=attachment)

    def start_command_task(
        self,
        command: str,
        attachment: dict | None = None,
    ) -> None:
        self.set_working_state(True)
        self.show_thinking_loader()

        def run_command(
            cancellation_token,
            progress_callback,
        ):
            if attachment is not None:
                return self.assistant.handle_image_command(
                    command=command,
                    attachment=attachment,
                    cancellation_token=cancellation_token,
                    stage_callback=progress_callback,
                )

            return self.assistant.handle_command(
                command=command,
                confirmation_callback=self.request_confirmation,
                progress_callback=(
                    lambda step_number, total_steps, step:
                    progress_callback(
                        "Executing",
                        step_number,
                        total_steps,
                        step,
                    )
                ),
                cancellation_token=cancellation_token,
                stage_callback=progress_callback,
            )

        self.active_task_id = self.task_manager.start(run_command)

    def cancel_active_task(self) -> None:
        if self.task_manager.cancel(
            self.active_task_id
        ):
            self.set_status(
                "CANCELLING//",
                self.WARNING,
            )
            self.send_button.setEnabled(
                False
            )
            self.send_button.setText("…")

    def handle_task_progress(
        self,
        task_id,
        stage,
        current,
        total,
        detail,
    ) -> None:
        if task_id != self.active_task_id:
            return

        if total:
            text = (
                f"{stage.upper()}//"
                f"{current}/{total}"
            )
        else:
            text = (
                f"{stage.upper()}//"
            )

        self.set_status(
            text,
            self.INFO,
        )

    def handle_task_completed(
        self,
        task_id,
        report,
    ) -> None:
        if task_id != self.active_task_id:
            return

        self.active_task_id = None
        self.display_report(
            report
        )
        self.set_working_state(False)

        is_screenshot_capture = (
            report.success
            and any(
                result.tool == "screenshot"
                and result.action in {"capture", "take", "screenshot"}
                for result in report.results
            )
        )

        if is_screenshot_capture:
            self.notify_desktop(
                "Screenshot captured",
                "Saved to Pictures > MV.AI Screenshots",
                QSystemTrayIcon.MessageIcon.Information,
            )
        elif self.isMinimized() or not self.isActiveWindow():
            title = (
                "MV.AI task complete"
                if report.success
                else "MV.AI task failed"
            )
            self.notify_desktop(
                title,
                report.message
                or "The task finished.",
                (
                    QSystemTrayIcon.MessageIcon.Information
                    if report.success
                    else QSystemTrayIcon.MessageIcon.Warning
                ),
            )

    def handle_task_failed(
        self,
        task_id,
        message,
    ) -> None:
        if task_id != self.active_task_id:
            return

        self.active_task_id = None
        self.display_command_error(
            message
        )
        self.set_working_state(False)
        self.notify_desktop(
            "MV.AI encountered an error",
            message,
            QSystemTrayIcon.MessageIcon.Critical,
        )

    def handle_task_cancelled(
        self,
        task_id,
    ) -> None:
        if task_id != self.active_task_id:
            return

        self.active_task_id = None
        self.hide_thinking_loader()
        self.add_message(
            "Task cancelled.",
            "step",
        )
        self.set_working_state(False)
        self.notify_desktop(
            "MV.AI task cancelled",
            "The running task was stopped.",
        )

    def display_report(
        self,
        report,
    ):
        self.hide_thinking_loader()

        if report.success:
            outputs = []

            for result in report.results:
                if result.output is not None:
                    output = str(
                        result.output
                    ).strip()

                    if output:
                        outputs.append(output)

            response = (
                "\n".join(outputs)
                if outputs
                else (
                    report.message
                    or "Task completed successfully."
                )
            )

            self.add_message(
                response,
                "assistant",
            )

            if (
                self.voice_enabled
                and self.voice_assistant is not None
            ):
                self.voice_assistant.speak(
                    self.prepare_spoken_response(
                        response
                    )
                )

        else:
            message = merge_error_messages(
                report.message,
                (result.error for result in report.results),
            )

            if not message:
                message = (
                    "The task could not be completed."
                )

            self.add_message(
                message,
                "error",
            )

            # Do not speak failure messages. Speaking an API error can leave
            # the status stuck on SPEAKING// while the service is unavailable.
            self.reset_voice_after_error()

    def display_command_error(
        self,
        message,
    ):
        self.hide_thinking_loader()

        self.add_message(
            message,
            "error",
        )

        # Errors stay visible in the chat but are not read aloud.
        self.reset_voice_after_error()

    # --------------------------------------------------
    # Progress and confirmation
    # --------------------------------------------------

    def emit_progress(
        self,
        step_number,
        total_steps,
        step,
    ):
        self.bridge.progress.emit(
            step_number,
            total_steps,
            step,
        )

    def show_progress(
        self,
        step_number,
        total_steps,
        step,
    ):
        description = getattr(
            step,
            "description",
            "",
        )
        label = (
            description
            or f"Working {step_number}/{total_steps}"
        )
        self.set_status(
            f"{label} // {step_number}/{total_steps}",
            self.INFO,
        )

    def request_confirmation(
        self,
        message,
        step,
    ):
        event = threading.Event()
        result = {
            "confirmed": False,
        }

        self.bridge.confirmation_requested.emit(
            message,
            step,
            event,
            result,
        )

        event.wait()

        return result["confirmed"]

    def handle_confirmation_request(
        self,
        message,
        step,
        event,
        result,
    ):
        dialog_title = "MV.AI Permission"
        details = f"{message}\n\nTask: {step.description}"

        step_args = getattr(step, "args", {}) or {}
        action = str(step_args.get("action", "")).strip().lower()

        if getattr(step, "tool", "") == "memory" and action in {
            "update_memory",
            "forget_memory",
        }:
            dialog_title = (
                "Confirm memory update"
                if action == "update_memory"
                else "Confirm forgetting memory"
            )
            details = (
                f"{message}\n\n"
                f"Memory: {step_args.get('query', '')}"
            )
            if action == "update_memory":
                details += (
                    f"\nNew value: {step_args.get('value', '')}"
                )


        if getattr(step, "tool", "") == "email" and action == "send_email":
            dialog_title = "Review email before sending"
            body_mode = str(
                step_args.get("body_mode", "")
            ).strip().lower()

            if body_mode == "composed":
                draft_notice = (
                    "Draft type: Composed from your topic. "
                    "Review the full message carefully."
                )
            elif body_mode == "exact":
                draft_notice = (
                    "Draft type: Your exact requested message."
                )
            else:
                draft_notice = (
                    "Review the full message carefully."
                )

            details = (
                f"{message}\n\n"
                f"{draft_notice}\n\n"
                f"To: {step_args.get('to', '')}\n"
                f"Subject: {step_args.get('subject', '')}\n\n"
                f"Message:\n{step_args.get('body', '')}"
            )

        answer = QMessageBox.question(
            self,
            dialog_title,
            details,
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )

        result["confirmed"] = (
            answer
            == QMessageBox.StandardButton.Yes
        )

        event.set()

    def show_plugin_warnings(self) -> None:
        """Surface plugin loading failures inside the desktop interface."""

        errors = self.assistant.get_plugin_errors()
        if not errors:
            return

        self.set_status("TOOL WARNING", self.WARNING)
        self.add_message(
            "Some tools could not load:\n"
            + "\n".join(f"• {error}" for error in errors),
            "error",
        )

    # --------------------------------------------------
    # Voice
    # --------------------------------------------------

    def start_voice_timer(self):
        from PySide6.QtCore import QTimer

        QTimer.singleShot(
            700,
            self.start_voice_mode,
        )

    def start_voice_mode(self):
        if self.voice_enabled:
            return

        try:
            self.voice_assistant = VoiceAssistant(
                command_callback=(
                    self.bridge.voice_command.emit
                ),
                status_callback=(
                    self.bridge.voice_status.emit
                ),
                message_callback=(
                    self.bridge.voice_message.emit
                ),
            )

            started = (
                self.voice_assistant.start()
            )

            if not started:
                self.voice_assistant = None
                self.voice_enabled = False
                self.set_status(
                    "Voice unavailable",
                    self.ERROR,
                )
                return

            self.voice_enabled = True
            self.microphone_button.setStyleSheet(
                f"""
                QPushButton {{
                    background: #1B2030;
                    color: {self.SUCCESS};
                    border: none;
                    border-radius: 24px;
                    font-size: 18px;
                }}

                QPushButton:hover {{
                    background: #252C40;
                }}
                """
            )

        except Exception as error:
            self.voice_enabled = False
            self.voice_assistant = None
            self.add_message(
                f"Voice mode could not start: {error}",
                "error",
            )
            self.set_status(
                "Voice unavailable",
                self.ERROR,
            )

    def stop_voice_mode(self):
        if self.voice_assistant is not None:
            try:
                self.voice_assistant.stop()
            except Exception:
                pass

        self.voice_assistant = None
        self.voice_enabled = False

        if not self.is_working:
            self.set_status(
                "MIC//OFF",
                self.MUTED,
            )

    def microphone_clicked(self):
        if self.voice_enabled:
            self.stop_voice_mode()
        else:
            self.start_voice_mode()

    def handle_voice_command(
        self,
        command,
    ):
        command = command.strip()

        if not command:
            return

        if self.is_working:
            if self.voice_assistant is not None:
                self.voice_assistant.speak(
                    "I am still working on the previous task."
                )
            return

        self.add_message(
            command,
            "user",
        )

        self.start_command_task(
            command
        )

    def apply_voice_status(
        self,
        status,
    ):
        if status == "__working_finished__":
            self.set_working_state(False)
            return

        if self.is_working and status != "Thinking":
            return

        lowered = status.lower()

        if "unavailable" in lowered or "retrying" in lowered:
            # Network speech-recognition failures are normally temporary.
            # The voice worker retries and restores listening automatically.
            display_text = "VOICE//RETRYING"
            color = self.WARNING

        elif "error" in lowered:
            display_text = "VOICE//ERROR"
            color = self.ERROR

        elif "calibrating" in lowered:
            display_text = "CALIBRATING..."
            color = self.WARNING

        elif "awake" in lowered:
            display_text = "AWAKE//INPUT"
            color = self.INFO

        elif "waiting" in lowered:
            display_text = "WAITING//VOICE"
            color = self.INFO

        elif "thinking" in lowered:
            display_text = "THINKING//"
            color = self.WARNING

        elif "speaking" in lowered:
            display_text = "SPEAKING//"
            color = self.INFO

        elif "listening" in lowered:
            display_text = "LISTENING//HEY MV"
            color = self.SUCCESS

        else:
            display_text = status
            color = self.SUCCESS

        self.set_status(
            display_text,
            color,
        )

    def show_voice_message(
        self,
        message,
    ):
        if message == "__scroll__":
            return

        print(f"[VOICE] {message}")

    # --------------------------------------------------
    # State
    # --------------------------------------------------

    def set_status(
        self,
        text,
        color,
    ):
        self.status_label.glitch_to(
            text
        )

        self.status_dot.setStyleSheet(
            f"color: {color}; font-size: 11px;"
        )

    def set_working_state(
        self,
        working,
    ):
        self.is_working = working

        self.command_entry.setEnabled(
            not working
        )
        if hasattr(self, "add_stuff_button"):
            self.add_stuff_button.setEnabled(not working)
        if hasattr(self, "image_attachment_preview"):
            self.image_attachment_preview.remove_button.setEnabled(not working)
        self.send_button.setEnabled(True)
        self.send_button.setText(
            "■" if working else "➤"
        )
        self.send_button.setToolTip(
            "Cancel task"
            if working
            else "Send command"
        )

        # Keep navigation and the More panel available while a
        # background command is running.
        for button_name in (
            "new_reality_button",
            "recent_realities_button",
            "sparks_button",
            "more_button",
        ):
            if hasattr(self, button_name):
                getattr(
                    self,
                    button_name,
                ).setEnabled(True)

        if not working:
            self.command_entry.setFocus()

            if self.voice_enabled:
                self.set_status(
                    "LISTENING//HEY MV",
                    self.SUCCESS,
                )
            else:
                self.set_status(
                    "MIC//OFF",
                    self.MUTED,
                )

    def reset_voice_after_error(self) -> None:
        """Return voice mode to listening without speaking the error."""

        if self.voice_assistant is not None:
            try:
                self.voice_assistant.reset_after_error()
            except Exception as error:
                print(f"[VOICE RESET WARNING] {error}")

        if self.voice_enabled:
            self.set_status(
                "LISTENING//HEY MV",
                self.SUCCESS,
            )

    @staticmethod
    def prepare_spoken_response(
        response,
    ):
        clean = " ".join(
            response.split()
        ).strip()

        # Do not read long addresses, subjects, and timing numbers aloud.
        # The full result remains visible in the chat bubble.
        if clean.lower().startswith("email sent to "):
            return "Email sent successfully."

        if len(clean) <= 260:
            return clean

        return clean[:257].rstrip() + "..."

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------

    def closeEvent(self, event):
        self.task_manager.cancel_all()
        self.stop_voice_mode()

        if hasattr(self, "notification_tray"):
            self.notification_tray.hide()

        if self.thinking_loader is not None:
            self.thinking_loader.stop()

        try:
            self.assistant.shutdown()
        except Exception:
            pass

        event.accept()