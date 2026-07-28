from PySide6.QtCore import (
    QEasingCurve,
    QEvent,
    QParallelAnimationGroup,
    QPropertyAnimation,
    Qt,
    Signal,
)
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
)


class RealityDockButton(QFrame):
    """
    Reusable icon-first Reality Dock button.

    Collapsed:
        ⊕

    Expanded on hover:
        ⊕  New Reality

    The icon and label are separate widgets so the icon can stay
    larger without making the text oversized.
    """

    activated = Signal()

    def __init__(
        self,
        icon_text: str = "⊕",
        label_text: str = "New Reality",
        collapsed_width: int = 48,
        expanded_width: int = 178,
        parent=None,
    ):
        super().__init__(parent)

        self.icon_text = icon_text
        self.label_text = label_text
        self.collapsed_width = collapsed_width
        self.expanded_width = expanded_width
        self.is_expanded = False

        self.setObjectName("realityDockButton")
        self.setFixedHeight(46)
        self.setMinimumWidth(self.collapsed_width)
        self.setMaximumWidth(self.collapsed_width)
        self.setCursor(
            Qt.CursorShape.PointingHandCursor
        )
        self.setFocusPolicy(
            Qt.FocusPolicy.StrongFocus
        )

        self.setStyleSheet(
            """
            QFrame#realityDockButton {
                background: #151927;
                border: 1px solid #2A3042;
                border-radius: 23px;
            }

            QFrame#realityDockButton[hovered="true"] {
                background: #1B2030;
                border-color: #4A4675;
            }

            QFrame#realityDockButton[pressed="true"] {
                background: #20263A;
                border-color: #6258A0;
            }

            QFrame#realityDockButton:disabled {
                background: #121520;
                border-color: #222738;
            }
            """
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            0,
            0,
            14,
            0,
        )
        layout.setSpacing(8)

        self.icon_label = QLabel(
            self.icon_text
        )
        self.icon_label.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        self.icon_label.setFixedWidth(
            self.collapsed_width - 2
        )
        self.icon_label.setStyleSheet(
            """
            QLabel {
                color: #F5F7FB;
                background: transparent;
                border: none;
                font-family: "Segoe UI Symbol";
                font-size: 21px;
                font-weight: 500;
            }
            """
        )

        self.text_label = QLabel(
            self.label_text
        )
        self.text_label.setStyleSheet(
            """
            QLabel {
                color: #F5F7FB;
                background: transparent;
                border: none;
                font-family: "Segoe UI";
                font-size: 13px;
                font-weight: 600;
            }
            """
        )
        self.text_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.icon_label.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents,
            True,
        )

        self.text_opacity = QGraphicsOpacityEffect(
            self.text_label
        )
        self.text_label.setGraphicsEffect(
            self.text_opacity
        )
        self.text_opacity.setOpacity(0.0)

        layout.addWidget(
            self.icon_label
        )
        layout.addWidget(
            self.text_label
        )
        layout.addStretch(1)

        self.width_min_animation = QPropertyAnimation(
            self,
            b"minimumWidth",
            self,
        )
        self.width_max_animation = QPropertyAnimation(
            self,
            b"maximumWidth",
            self,
        )
        self.text_animation = QPropertyAnimation(
            self.text_opacity,
            b"opacity",
            self,
        )

        self.animation_group = QParallelAnimationGroup(
            self
        )
        self.animation_group.addAnimation(
            self.width_min_animation
        )
        self.animation_group.addAnimation(
            self.width_max_animation
        )
        self.animation_group.addAnimation(
            self.text_animation
        )

        # Slower and calmer than the first version.
        self.animation_group.setDirection(
            QParallelAnimationGroup.Direction.Forward
        )

        for animation in (
            self.width_min_animation,
            self.width_max_animation,
        ):
            animation.setDuration(340)
            animation.setEasingCurve(
                QEasingCurve.Type.OutCubic
            )

        self.text_animation.setDuration(280)
        self.text_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic
        )

        self.setProperty(
            "hovered",
            False,
        )
        self.setProperty(
            "pressed",
            False,
        )

    def enterEvent(self, event: QEvent) -> None:
        if self.isEnabled():
            self.setProperty(
                "hovered",
                True,
            )
            self.refresh_style()
            self.expand()

        super().enterEvent(event)

    def leaveEvent(self, event: QEvent) -> None:
        self.setProperty(
            "hovered",
            False,
        )
        self.setProperty(
            "pressed",
            False,
        )
        self.refresh_style()
        self.collapse()

        super().leaveEvent(event)

    def mousePressEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        if (
            self.isEnabled()
            and event.button()
            == Qt.MouseButton.LeftButton
        ):
            self.setProperty(
                "pressed",
                True,
            )
            self.refresh_style()

        super().mousePressEvent(event)

    def mouseReleaseEvent(
        self,
        event: QMouseEvent,
    ) -> None:
        was_pressed = bool(
            self.property("pressed")
        )

        self.setProperty(
            "pressed",
            False,
        )
        self.refresh_style()

        if (
            was_pressed
            and self.isEnabled()
            and event.button()
            == Qt.MouseButton.LeftButton
            and self.rect().contains(
                event.position().toPoint()
            )
        ):
            self.activated.emit()

        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if (
            self.isEnabled()
            and event.key()
            in {
                Qt.Key.Key_Return,
                Qt.Key.Key_Enter,
                Qt.Key.Key_Space,
            }
        ):
            self.activated.emit()
            event.accept()
            return

        super().keyPressEvent(event)

    def expand(self) -> None:
        self.is_expanded = True
        self.animate_to(
            width=self.expanded_width,
            opacity=1.0,
        )

    def collapse(self) -> None:
        self.is_expanded = False
        self.animate_to(
            width=self.collapsed_width,
            opacity=0.0,
        )

    def animate_to(
        self,
        width: int,
        opacity: float,
    ) -> None:
        self.animation_group.stop()

        current_width = self.width()
        current_opacity = (
            self.text_opacity.opacity()
        )

        self.width_min_animation.setStartValue(
            current_width
        )
        self.width_min_animation.setEndValue(
            width
        )

        self.width_max_animation.setStartValue(
            current_width
        )
        self.width_max_animation.setEndValue(
            width
        )

        self.text_animation.setStartValue(
            current_opacity
        )
        self.text_animation.setEndValue(
            opacity
        )

        self.animation_group.start()

    def refresh_style(self) -> None:
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()