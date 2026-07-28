from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from core.app_paths import get_app_data_dir, get_logs_dir


class MorePopup(QDialog):
    """Centered MV.ai settings and information panel.

    The dialog covers the parent window with a dim backdrop. Its main panel
    stays centered and uses a horizontal dock of round category buttons.
    """

    PANEL_MAX_WIDTH = 940
    PANEL_MAX_HEIGHT = 620
    PANEL_MIN_WIDTH = 720
    PANEL_MIN_HEIGHT = 520

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
        )
        self.setWindowModality(Qt.WindowModality.WindowModal)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setObjectName("moreDialog")

        self._pages: dict[str, int] = {}
        self._nav_buttons: dict[str, QPushButton] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        self.backdrop = QFrame()
        self.backdrop.setObjectName("moreBackdrop")
        self.backdrop.installEventFilter(self)
        root.addWidget(self.backdrop)

        backdrop_layout = QVBoxLayout(self.backdrop)
        backdrop_layout.setContentsMargins(24, 24, 24, 24)
        backdrop_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.panel = QFrame()
        self.panel.setObjectName("morePanel")
        self.panel.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Fixed,
        )
        backdrop_layout.addWidget(self.panel)

        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(26, 22, 26, 24)
        panel_layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(12)

        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title = QLabel("MV.AI CONTROL CENTER")
        title.setObjectName("popupTitle")
        subtitle = QLabel("Settings, profile, voice, data and app information")
        subtitle.setObjectName("popupSubtitle")

        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header.addLayout(title_box)
        header.addStretch(1)

        close_button = QPushButton("×")
        close_button.setObjectName("closeButton")
        close_button.setFixedSize(40, 40)
        close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        close_button.setToolTip("Close")
        close_button.clicked.connect(self.reject)
        header.addWidget(close_button)
        panel_layout.addLayout(header)

        self.nav_frame = QFrame()
        self.nav_frame.setObjectName("topDock")
        nav_layout = QHBoxLayout(self.nav_frame)
        nav_layout.setContentsMargins(12, 9, 12, 9)
        nav_layout.setSpacing(12)
        nav_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.button_group = QButtonGroup(self)
        self.button_group.setExclusive(True)

        nav_items = [
            ("general", "⚙", "General"),
            ("profile", "♙", "Profile"),
            ("voice", "🎙", "Voice"),
            ("data", "⛨", "Data & privacy"),
            ("about", "✦", "About MV.ai"),
        ]

        for key, icon, tooltip in nav_items:
            button = QPushButton(icon)
            button.setObjectName("dockButton")
            button.setCheckable(True)
            button.setFixedSize(52, 52)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setToolTip(tooltip)
            button.setProperty("tabKey", key)

            icon_font = QFont("Segoe UI Symbol")
            icon_font.setPointSize(17)
            button.setFont(icon_font)

            self.button_group.addButton(button)
            self._nav_buttons[key] = button
            nav_layout.addWidget(button)
            button.clicked.connect(
                lambda checked=False, tab_key=key: self.show_page(tab_key)
            )

        panel_layout.addWidget(
            self.nav_frame,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        self.page_heading = QLabel("General")
        self.page_heading.setObjectName("pageHeading")
        panel_layout.addWidget(self.page_heading)

        self.stack = QStackedWidget()
        self.stack.setObjectName("settingsStack")
        panel_layout.addWidget(self.stack, 1)

        self._add_page("general", "General", self._build_general_page())
        self._add_page("profile", "Profile", self._build_profile_page())
        self._add_page("voice", "Voice", self._build_voice_page())
        self._add_page("data", "Data & privacy", self._build_data_page())
        self._add_page("about", "About MV.ai", self._build_about_page())

        self.setStyleSheet(self._stylesheet())
        self.show_page("general")

    def _add_page(self, key: str, heading: str, page: QWidget) -> None:
        index = self.stack.addWidget(page)
        self._pages[key] = index
        page.setProperty("heading", heading)

    def show_page(self, key: str) -> None:
        if key not in self._pages:
            return

        self.stack.setCurrentIndex(self._pages[key])
        self.page_heading.setText(
            str(self.stack.currentWidget().property("heading"))
        )

        for name, button in self._nav_buttons.items():
            active = name == key
            button.setChecked(active)
            button.setProperty("active", active)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()

    def _page_container(self) -> tuple[QScrollArea, QVBoxLayout]:
        scroll = QScrollArea()
        scroll.setObjectName("pageScroll")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        content = QWidget()
        content.setObjectName("pageContent")
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 8, 0)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(content)
        return scroll, layout

    def _section(
        self,
        title: str,
        description: str,
        actions: list[tuple[str, callable]] | None = None,
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsCard")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 15, 18, 15)
        layout.setSpacing(8)

        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        layout.addWidget(heading)

        body = QLabel(description)
        body.setObjectName("cardDescription")
        body.setWordWrap(True)
        body.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        layout.addWidget(body)

        if actions:
            action_row = QHBoxLayout()
            action_row.setSpacing(9)
            action_row.addStretch(1)
            for label, callback in actions:
                button = QPushButton(label)
                button.setObjectName("actionButton")
                button.setCursor(Qt.CursorShape.PointingHandCursor)
                button.clicked.connect(callback)
                action_row.addWidget(button)
            layout.addLayout(action_row)

        return card

    def _build_general_page(self) -> QWidget:
        scroll, layout = self._page_container()
        layout.addWidget(
            self._section(
                "Desktop assistant",
                "MV.ai is running as a Windows desktop assistant with local "
                "tools, editable profile context, voice input, long-term "
                "memory and Gemini-powered reasoning.",
            )
        )
        layout.addWidget(
            self._section(
                "Quick access",
                "Open MV.ai's local data or diagnostic logs without hunting "
                "through AppData folders.",
                [
                    ("Open MV.ai data", lambda: self.open_folder(get_app_data_dir())),
                    ("Open logs", lambda: self.open_folder(get_logs_dir())),
                ],
            )
        )
        layout.addWidget(
            self._section(
                "Current foundation",
                "Python + PySide6 interface • schema-driven tools • SQLite "
                "realities and memories • confirmation gates for sensitive "
                "actions.",
            )
        )
        return scroll

    def _build_profile_page(self) -> QWidget:
        scroll, layout = self._page_container()
        profile_path = self.project_root() / "user_profile.json"
        layout.addWidget(
            self._section(
                "Editable personal profile",
                "Permanent facts such as your name, nickname, projects and "
                "preferences are loaded from user_profile.json before each "
                "request. You can edit the file directly—no Python changes "
                "or restart required.",
                [("Edit profile", lambda: self.open_file(profile_path))],
            )
        )
        layout.addWidget(
            self._section(
                "Profile location",
                str(profile_path),
            )
        )
        layout.addWidget(
            self._section(
                "Keep secrets elsewhere",
                "Do not place API keys, passwords, banking information or "
                "exact private addresses in the profile. Relevant profile "
                "context may be included in requests sent to Gemini.",
            )
        )
        return scroll

    def _build_voice_page(self) -> QWidget:
        scroll, layout = self._page_container()
        microphone_test = self.project_root() / "test_microphone.py"
        layout.addWidget(
            self._section(
                "Wake and speech",
                "Wake phrase: Hey MV\nSpeech recognition: microphone input\n"
                "Speech output: Windows text-to-speech with timeout recovery.",
            )
        )
        layout.addWidget(
            self._section(
                "Microphone diagnostics",
                "Run the existing microphone test when wake-word detection "
                "or recognition behaves inconsistently.",
                [
                    (
                        "Run microphone test",
                        lambda: self.run_script(microphone_test),
                    )
                ],
            )
        )
        layout.addWidget(
            self._section(
                "Voice safety",
                "MV.ai pauses listening while speaking and automatically "
                "returns to LISTENING//HEY MV after speech or an error.",
            )
        )
        return scroll

    def _build_data_page(self) -> QWidget:
        scroll, layout = self._page_container()
        layout.addWidget(
            self._section(
                "Local storage",
                "Realities, memories, backups and logs are stored locally on "
                "this computer. Use the buttons below to inspect those files.",
                [
                    ("Open data", lambda: self.open_folder(get_app_data_dir())),
                    ("Open logs", lambda: self.open_folder(get_logs_dir())),
                ],
            )
        )
        layout.addWidget(
            self._section(
                "AI requests",
                "When Gemini handles a request, the command and selected "
                "relevant context can be sent to Google's Gemini service. "
                "Local profile commands can still work without Gemini.",
            )
        )
        layout.addWidget(
            self._section(
                "Credentials",
                "Private keys and email credentials belong only in the local "
                ".env file. Never bundle or upload that file.",
            )
        )
        return scroll

    def _build_about_page(self) -> QWidget:
        scroll, layout = self._page_container()
        layout.addWidget(
            self._section(
                "MV.ai",
                "A personal desktop assistant created and designed by Pranav "
                "Khimani. Built with Python, PySide6 and Gemini.",
            )
        )
        layout.addWidget(
            self._section(
                "GNOSIS",
                "MV.ai is a GNOSIS project.\n\nOne assistant, many realities.",
            )
        )
        layout.addWidget(
            self._section(
                "Development status",
                "Desktop foundation under active development. The current "
                "focus is reliable tools, safe execution, memory and a "
                "cohesive interface.",
            )
        )
        return scroll

    def showEvent(self, event) -> None:  # noqa: N802 - Qt method name
        self._fit_to_parent()
        super().showEvent(event)

    def _fit_to_parent(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            self.resize(1180, 760)
            self.panel.setFixedSize(900, 600)
            return

        parent_geometry = parent.geometry()
        self.setGeometry(parent_geometry)

        available_width = max(520, parent.width() - 90)
        available_height = max(440, parent.height() - 90)

        panel_width = min(
            self.PANEL_MAX_WIDTH,
            max(self.PANEL_MIN_WIDTH, int(parent.width() * 0.62)),
            available_width,
        )
        panel_height = min(
            self.PANEL_MAX_HEIGHT,
            max(self.PANEL_MIN_HEIGHT, int(parent.height() * 0.70)),
            available_height,
        )
        self.panel.setFixedSize(panel_width, panel_height)

    def eventFilter(self, watched, event):  # noqa: N802 - Qt method name
        if (
            watched is self.backdrop
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            position = event.position().toPoint()
            if not self.panel.geometry().contains(position):
                self.reject()
                return True
        return super().eventFilter(watched, event)

    @staticmethod
    def project_root() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def open_folder(path: str | Path) -> None:
        folder = Path(path)
        folder.mkdir(parents=True, exist_ok=True)
        MorePopup._open_path(folder)

    @staticmethod
    def open_file(path: str | Path) -> None:
        target = Path(path)
        if not target.exists():
            return
        MorePopup._open_path(target)

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
        except OSError:
            return

    @staticmethod
    def run_script(path: str | Path) -> None:
        script = Path(path)
        if not script.exists():
            return

        try:
            creation_flags = 0
            if os.name == "nt":
                creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
            subprocess.Popen(
                [sys.executable, str(script)],
                cwd=str(script.parent),
                creationflags=creation_flags,
            )
        except OSError:
            return

    @staticmethod
    def _stylesheet() -> str:
        return """
            QDialog#moreDialog {
                background: transparent;
            }

            QFrame#moreBackdrop {
                background: rgba(3, 5, 10, 188);
            }

            QFrame#morePanel {
                background: #10131C;
                border: 1px solid #343B50;
                border-radius: 24px;
            }

            QLabel {
                background: transparent;
                border: none;
                color: #F5F7FB;
            }

            QLabel#popupTitle {
                color: #F7F8FC;
                font-size: 20px;
                font-weight: 750;
            }

            QLabel#popupSubtitle {
                color: #858DA0;
                font-size: 11px;
            }

            QPushButton#closeButton {
                background: #171C29;
                color: #E8EBF3;
                border: 1px solid #30384D;
                border-radius: 20px;
                font-size: 24px;
                padding: 0;
            }

            QPushButton#closeButton:hover {
                background: #232A3B;
                border-color: #5A6683;
            }

            QFrame#topDock {
                background: #151A27;
                border: 1px solid #2C3448;
                border-radius: 35px;
            }

            QPushButton#dockButton {
                background: #1A2030;
                color: #DDE2EE;
                border: 1px solid #30394F;
                border-radius: 26px;
                padding: 0;
            }

            QPushButton#dockButton:hover {
                background: #252C40;
                border-color: #7168C8;
            }

            QPushButton#dockButton[active="true"] {
                background: #6F61F6;
                color: white;
                border-color: #8C82FF;
            }

            QLabel#pageHeading {
                color: #F7F8FC;
                font-size: 18px;
                font-weight: 700;
                padding-left: 2px;
            }

            QStackedWidget#settingsStack {
                background: transparent;
                border: none;
            }

            QScrollArea#pageScroll,
            QWidget#pageContent {
                background: transparent;
                border: none;
            }

            QScrollBar:vertical {
                background: transparent;
                width: 8px;
                margin: 2px;
            }

            QScrollBar::handle:vertical {
                background: #333B50;
                border-radius: 4px;
                min-height: 28px;
            }

            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }

            QFrame#settingsCard {
                background: #151927;
                border: 1px solid #292F42;
                border-radius: 15px;
            }

            QLabel#cardTitle {
                color: #F1F3F8;
                font-size: 13px;
                font-weight: 700;
            }

            QLabel#cardDescription {
                color: #AEB5C5;
                font-size: 11px;
                line-height: 1.35;
            }

            QPushButton#actionButton {
                background: #1C2232;
                color: #ECEEF5;
                border: 1px solid #38415A;
                border-radius: 11px;
                padding: 8px 13px;
                font-size: 11px;
                font-weight: 600;
            }

            QPushButton#actionButton:hover {
                background: #292F46;
                border-color: #7469DC;
            }
        """
