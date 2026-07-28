from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ClickableImageLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ImageViewerDialog(QDialog):
    """Simple full-image preview that keeps the original aspect ratio."""

    def __init__(self, image_path: str | Path, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.setWindowTitle(self.image_path.name)
        self.resize(900, 680)
        self.setMinimumSize(560, 420)
        self.setModal(True)
        self.setStyleSheet(
            """
            QDialog { background: #080A10; }
            QScrollArea { background: #080A10; border: none; }
            QLabel { background: transparent; color: #F5F7FB; }
            QPushButton {
                background: #1B2030;
                color: #F5F7FB;
                border: 1px solid #30374C;
                border-radius: 16px;
                padding: 8px 16px;
            }
            QPushButton:hover { background: #252C40; }
            """
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel(self.image_path.name)
        title.setStyleSheet("font-size: 14px; font-weight: 600;")
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        header.addWidget(title)
        header.addStretch(1)
        header.addWidget(close_button)
        root.addLayout(header)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)

        image_label = QLabel()
        image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pixmap = QPixmap(str(self.image_path))
        if pixmap.isNull():
            image_label.setText("MV.ai could not open this image.")
        else:
            max_width = 1400
            max_height = 1000
            if pixmap.width() > max_width or pixmap.height() > max_height:
                pixmap = pixmap.scaled(
                    max_width,
                    max_height,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
            image_label.setPixmap(pixmap)

        container_layout.addWidget(image_label, 1)
        scroll.setWidget(container)
        root.addWidget(scroll, 1)


class ImageAttachmentPreview(QFrame):
    remove_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("imageAttachmentPreview")
        self.setStyleSheet(
            """
            QFrame#imageAttachmentPreview {
                background: #111522;
                border: 1px solid #2A3042;
                border-radius: 16px;
            }
            QLabel { background: transparent; border: none; }
            QPushButton {
                background: #242A3B;
                color: #DDE1EB;
                border: none;
                border-radius: 14px;
                font-size: 14px;
            }
            QPushButton:hover { background: #343B52; }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)

        self.thumbnail = QLabel()
        self.thumbnail.setFixedSize(56, 56)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.thumbnail.setStyleSheet(
            "background: #090B12; border-radius: 10px; color: #9299AA;"
        )

        text_layout = QVBoxLayout()
        text_layout.setSpacing(2)
        self.name_label = QLabel("Image")
        self.name_label.setStyleSheet("color: #F5F7FB; font-size: 13px; font-weight: 600;")
        self.info_label = QLabel("Ready to analyze")
        self.info_label.setStyleSheet("color: #9299AA; font-size: 11px;")
        text_layout.addWidget(self.name_label)
        text_layout.addWidget(self.info_label)

        self.remove_button = QPushButton("×")
        self.remove_button.setFixedSize(28, 28)
        self.remove_button.setToolTip("Remove image")
        self.remove_button.clicked.connect(self.remove_requested)

        layout.addWidget(self.thumbnail)
        layout.addLayout(text_layout, 1)
        layout.addWidget(self.remove_button)
        self.hide()

    def set_image(self, image_path: str | Path, size_bytes: int) -> None:
        path = Path(image_path)
        pixmap = QPixmap(str(path))
        if pixmap.isNull():
            raise ValueError("MV.ai could not preview this image.")

        preview = pixmap.scaled(
            52,
            52,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.thumbnail.setPixmap(preview)
        self.name_label.setText(path.name)
        self.info_label.setText(f"{format_file_size(size_bytes)} • ready for Gemini")
        self.show()

    def clear(self) -> None:
        self.thumbnail.clear()
        self.name_label.setText("Image")
        self.info_label.setText("Ready to analyze")
        self.hide()


class ChatImageWidget(QFrame):
    """Responsive image card embedded inside a chat bubble."""

    def __init__(self, image_path: str | Path, parent=None):
        super().__init__(parent)
        self.image_path = Path(image_path)
        self.original_pixmap = QPixmap(str(self.image_path))
        self.setStyleSheet("background: transparent; border: none;")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(6)

        self.image_label = ClickableImageLabel()
        self.image_label.setCursor(Qt.CursorShape.PointingHandCursor)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.image_label.setMinimumHeight(100)
        self.image_label.setStyleSheet(
            "background: #090B12; border: 1px solid #30364A; "
            "border-radius: 14px; padding: 4px;"
        )

        if self.original_pixmap.isNull():
            self.image_label.setText("Image unavailable")
            self.image_label.setFixedHeight(100)

        self.image_label.clicked.connect(self.open_viewer)
        hint = QLabel("Click image to preview")
        hint.setStyleSheet("color: #7F879A; font-size: 10px;")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.image_label)
        layout.addWidget(hint)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.update_preview()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.update_preview()

    def update_preview(self) -> None:
        if self.original_pixmap.isNull():
            return

        available_width = max(220, min(680, self.width() - 12))
        preview = self.original_pixmap.scaled(
            available_width,
            360,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image_label.setPixmap(preview)
        self.image_label.setFixedHeight(max(100, preview.height() + 8))

    def open_viewer(self) -> None:
        if self.image_path.exists():
            ImageViewerDialog(self.image_path, self.window()).exec()


def format_file_size(size_bytes: int) -> str:
    size = float(size_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size_bytes} B"
