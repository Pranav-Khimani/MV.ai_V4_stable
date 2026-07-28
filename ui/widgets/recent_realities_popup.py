from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class RecentRealitiesPopup(QDialog):
    """
    Floating panel that displays saved conversation sessions.
    """

    reality_selected = Signal(str)
    clear_requested = Signal()

    def __init__(
        self,
        realities=None,
        parent=None,
    ):
        super().__init__(parent)

        self.realities = realities or []

        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setModal(False)
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setFixedSize(
            350,
            410,
        )

        self.build_ui()

        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("recentRealityPanel")
        panel.setStyleSheet(
            """
            QFrame#recentRealityPanel {
                background: #111520;
                border: 1px solid #2A3042;
                border-radius: 22px;
            }
            """
        )

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(18, 17, 18, 16)
        layout.setSpacing(12)

        title_row = QHBoxLayout()

        title = QLabel("Recent Realities")
        title.setStyleSheet(
            """
            QLabel {
                color: #F5F7FB;
                background: transparent;
                border: none;
                font-size: 15px;
                font-weight: 700;
            }
            """
        )

        count = QLabel(str(len(self.realities)))
        count.setAlignment(Qt.AlignmentFlag.AlignCenter)
        count.setFixedSize(30, 24)
        count.setStyleSheet(
            """
            QLabel {
                color: #A89FFF;
                background: #1A1F30;
                border: 1px solid #30374D;
                border-radius: 12px;
                font-size: 11px;
                font-weight: 600;
            }
            """
        )

        self.clear_button = QPushButton("−")
        self.clear_button.setToolTip(
            "Clear all recent realities"
        )
        self.clear_button.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.clear_button.setFixedSize(
            26,
            26,
        )
        self.clear_button.setVisible(
            bool(self.realities)
        )
        self.clear_button.clicked.connect(
            self.clear_requested.emit
        )
        self.clear_button.setStyleSheet(
            """
            QPushButton {
                color: #A7ADBC;
                background: #181D2B;
                border: 1px solid #30374D;
                border-radius: 13px;
                font-size: 17px;
                font-weight: 600;
                padding-bottom: 2px;
            }

            QPushButton:hover {
                color: #FF8B98;
                background: #251A23;
                border-color: #60303C;
            }

            QPushButton:pressed {
                background: #321F29;
            }
            """
        )

        title_row.addWidget(title)
        title_row.addStretch(1)
        title_row.addWidget(
            self.clear_button
        )
        title_row.addSpacing(4)
        title_row.addWidget(count)
        layout.addLayout(title_row)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #252B3B;")
        layout.addWidget(divider)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 6px;
            }

            QScrollBar::handle:vertical {
                background: #30374A;
                border-radius: 3px;
                min-height: 28px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0px;
            }
            """
        )

        content = QWidget()
        content.setStyleSheet("background: transparent;")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(8)

        if not self.realities:
            empty = QLabel(
                "No saved realities yet.\n"
                "Start chatting, then create a New Reality."
            )
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty.setWordWrap(True)
            empty.setStyleSheet(
                """
                QLabel {
                    color: #7F8799;
                    background: transparent;
                    border: none;
                    font-size: 12px;
                    padding: 60px 20px;
                }
                """
            )
            content_layout.addWidget(empty)
        else:
            for reality in self.realities:
                content_layout.addWidget(
                    self.create_reality_item(reality)
                )

        content_layout.addStretch(1)
        scroll.setWidget(content)
        layout.addWidget(scroll, 1)
        root.addWidget(panel)

    def eventFilter(self, watched, event):
        """Close the panel when the user clicks outside it."""

        if (
            self.isVisible()
            and event.type()
            == QEvent.Type.MouseButtonPress
        ):
            global_position = (
                event.globalPosition().toPoint()
            )

            if not self.frameGeometry().contains(
                global_position
            ):
                self.close()

        return super().eventFilter(
            watched,
            event,
        )

    def closeEvent(self, event):
        """Clean up the application-wide event filter."""

        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)

        super().closeEvent(event)

    def create_reality_item(self, reality):
        button = QPushButton()
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setMinimumHeight(62)
        button.setStyleSheet(
            """
            QPushButton {
                background: #151A27;
                border: 1px solid #252C3D;
                border-radius: 14px;
                text-align: left;
            }

            QPushButton:hover {
                background: #1B2131;
                border-color: #3C4561;
            }

            QPushButton:pressed {
                background: #20263A;
            }
            """
        )

        item_layout = QVBoxLayout(button)
        item_layout.setContentsMargins(13, 10, 13, 10)
        item_layout.setSpacing(3)

        title = QLabel(
            reality.get("title", "New Reality")
        )
        title.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        title.setStyleSheet(
            """
            QLabel {
                color: #F5F7FB;
                background: transparent;
                border: none;
                font-size: 13px;
                font-weight: 600;
            }
            """
        )

        subtitle = QLabel(
            reality.get("subtitle", "")
        )
        subtitle.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )
        subtitle.setStyleSheet(
            """
            QLabel {
                color: #7F8799;
                background: transparent;
                border: none;
                font-size: 11px;
            }
            """
        )

        item_layout.addWidget(title)
        item_layout.addWidget(subtitle)

        session_id = str(reality.get("id", ""))

        button.clicked.connect(
            lambda checked=False, selected=session_id:
            self.select_reality(selected)
        )

        return button

    def select_reality(self, session_id: str) -> None:
        if not session_id:
            return

        self.reality_selected.emit(session_id)
        self.close()