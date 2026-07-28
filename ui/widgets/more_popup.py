from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from core.app_paths import (
    get_app_data_dir,
    get_logs_dir,
)


class MorePopup(QDialog):
    """Large floating information and quick-access panel."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowFlags(
            Qt.WindowType.Popup
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground,
            True,
        )
        self.setFixedSize(520, 450)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        panel = QFrame()
        panel.setObjectName("morePanel")
        panel.setStyleSheet(
            """
            QFrame#morePanel {
                background: #10131C;
                border: 1px solid #343B50;
                border-radius: 25px;
            }

            QLabel {
                background: transparent;
                border: none;
                color: #F5F7FB;
            }

            QPushButton {
                background: #171C29;
                color: #F5F7FB;
                border: 1px solid #30384D;
                border-radius: 13px;
                padding: 11px 14px;
                font-size: 12px;
                font-weight: 600;
            }

            QPushButton:hover {
                background: #20263A;
                border-color: #6258A0;
            }
            """
        )
        root.addWidget(panel)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 24, 26, 24)
        layout.setSpacing(15)

        title = QLabel("MV.AI")
        title.setStyleSheet(
            "font-size: 26px; font-weight: 750;"
        )
        layout.addWidget(title)

        subtitle = QLabel(
            "Flagship desktop assistant • v0.8"
        )
        subtitle.setStyleSheet(
            "color: #9299AA; font-size: 12px;"
        )
        layout.addWidget(subtitle)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(
            "background: #282E40; border: none;"
        )
        layout.addWidget(divider)

        credits_heading = QLabel("CREDITS")
        credits_heading.setStyleSheet(
            "color: #7A6CFF; font-size: 10px; "
            "font-weight: 800;"
        )
        layout.addWidget(credits_heading)

        credits = QLabel(
            "Created and designed by Pranav Khimani\n"
            "Built with Python, PySide6 and Gemini\n"
            "A GNOSIS product"
        )
        credits.setWordWrap(True)
        credits.setStyleSheet(
            "color: #DDE1EA; font-size: 13px;"
        )
        layout.addWidget(credits)

        details = QLabel(
            "Privacy  •  Memories and settings stay locally on this PC.\n"
            "Reliability  •  Crash logs and database backups are enabled.\n"
            "Status  •  Desktop foundation under active development."
        )
        details.setWordWrap(True)
        details.setStyleSheet(
            """
            color: #AEB5C5;
            background: #151927;
            border: 1px solid #292F42;
            border-radius: 16px;
            padding: 14px;
            font-size: 11px;
            """
        )
        layout.addWidget(details)

        actions = QHBoxLayout()
        actions.setSpacing(10)

        data_button = QPushButton(
            "Open MV.AI Data"
        )
        logs_button = QPushButton(
            "Open Logs"
        )

        data_button.clicked.connect(
            lambda: self.open_folder(
                get_app_data_dir()
            )
        )
        logs_button.clicked.connect(
            lambda: self.open_folder(
                get_logs_dir()
            )
        )

        actions.addWidget(data_button)
        actions.addWidget(logs_button)
        layout.addLayout(actions)

        layout.addStretch(1)

        footer = QLabel(
            "One assistant, many realities."
        )
        footer.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        footer.setStyleSheet(
            "color: #697083; font-size: 10px;"
        )
        layout.addWidget(footer)

    @staticmethod
    def open_folder(path: str | Path) -> None:
        folder = Path(path)
        folder.mkdir(
            parents=True,
            exist_ok=True,
        )

        if os.name == "nt":
            os.startfile(str(folder))
