from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QFont, QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QDialog,
    QFormLayout,
    QFrame,
    QHeaderView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.app_paths import get_app_data_dir, get_logs_dir
from memory.user_profile import UserProfile


class MorePopup(QDialog):
    """Centered MV.ai settings and information panel.

    The dialog covers the parent window with a dim backdrop. Its main panel
    stays centered and uses a horizontal dock of round category buttons.
    """

    PANEL_MAX_WIDTH = 940
    PANEL_MAX_HEIGHT = 620
    PANEL_MIN_WIDTH = 720
    PANEL_MIN_HEIGHT = 520

    PROFILE_SECTIONS = (
        (
            "Personal",
            (
                ("personal", "name", "Name", "Pranav"),
                ("personal", "nickname", "Nickname", "Multiverse"),
                (
                    "personal",
                    "preferred_name",
                    "Preferred name",
                    "What MV.ai should call you",
                ),
                ("personal", "age", "Age", "16"),
                ("personal", "birthday", "Birthday", "26/4/2010"),
            ),
        ),
        (
            "Education",
            (
                ("education", "role", "Role", "Student"),
                (
                    "education",
                    "grade_or_year",
                    "Grade or year",
                    "11",
                ),
                (
                    "education",
                    "old_school",
                    "Old school",
                    "Optional",
                ),
                ("education", "college", "College", "Optional"),
            ),
        ),
        (
            "Preferences",
            (
                (
                    "preferences",
                    "preferred_editor",
                    "Preferred editor",
                    "VS Code",
                ),
                ("preferences", "diet", "Diet", "Optional"),
                (
                    "preferences",
                    "communication_style",
                    "Communication style",
                    "Direct, concise, casual...",
                ),
            ),
        ),
        (
            "Projects",
            (
                (
                    "projects",
                    "main_project",
                    "Main project",
                    "MV.ai",
                ),
                ("projects", "company", "Company", "GNOSIS"),
            ),
        ),
    )

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
        self._profile_inputs: dict[tuple[str, str], QLineEdit] = {}
        self._profile_data: dict[str, Any] = {}
        self._profile_dirty = False
        self._loading_profile = False
        self.profile_status: QLabel | None = None
        self.custom_table: QTableWidget | None = None

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
        actions: list[tuple[str, Callable[[], None]]] | None = None,
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

        intro = QLabel(
            "Edit the facts MV.ai uses to understand you. Changes are saved "
            "to user_profile.json and are available on the very next command."
        )
        intro.setObjectName("profileIntro")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        for section_title, fields in self.PROFILE_SECTIONS:
            layout.addWidget(
                self._build_profile_fields_card(section_title, fields)
            )

        layout.addWidget(self._build_custom_facts_card())

        warning = QLabel(
            "Do not store passwords, API keys, bank details or exact private "
            "addresses here. Relevant profile facts may be sent to Gemini "
            "when it handles a request."
        )
        warning.setObjectName("profileWarning")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        footer = QFrame()
        footer.setObjectName("profileFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(14, 11, 14, 11)
        footer_layout.setSpacing(10)

        self.profile_status = QLabel("Loading profile…")
        self.profile_status.setObjectName("profileStatus")
        self.profile_status.setWordWrap(True)
        footer_layout.addWidget(self.profile_status, 1)

        reload_button = QPushButton("Reload")
        reload_button.setObjectName("secondaryButton")
        reload_button.setCursor(Qt.CursorShape.PointingHandCursor)
        reload_button.clicked.connect(self._load_profile_into_form)
        footer_layout.addWidget(reload_button)

        save_button = QPushButton("Save profile")
        save_button.setObjectName("saveProfileButton")
        save_button.setCursor(Qt.CursorShape.PointingHandCursor)
        save_button.clicked.connect(self._save_profile_from_form)
        footer_layout.addWidget(save_button)

        layout.addWidget(footer)
        self._load_profile_into_form()
        return scroll

    def _build_profile_fields_card(
        self,
        title: str,
        fields: tuple[tuple[str, str, str, str], ...],
    ) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 15, 18, 16)
        card_layout.setSpacing(11)

        heading = QLabel(title)
        heading.setObjectName("cardTitle")
        card_layout.addWidget(heading)

        form = QFormLayout()
        form.setContentsMargins(0, 0, 0, 0)
        form.setHorizontalSpacing(18)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
        )

        for section, key, label_text, placeholder in fields:
            label = QLabel(label_text)
            label.setObjectName("profileFieldLabel")

            field = QLineEdit()
            field.setObjectName("profileInput")
            field.setPlaceholderText(placeholder)
            field.setClearButtonEnabled(True)
            if section == "personal" and key == "age":
                field.setValidator(QIntValidator(0, 130, field))

            field.textChanged.connect(self._mark_profile_dirty)
            self._profile_inputs[(section, key)] = field
            form.addRow(label, field)

        card_layout.addLayout(form)
        return card

    def _build_custom_facts_card(self) -> QFrame:
        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 15, 18, 16)
        card_layout.setSpacing(10)

        heading = QLabel("Custom facts")
        heading.setObjectName("cardTitle")
        card_layout.addWidget(heading)

        description = QLabel(
            "Add anything that does not fit above, such as favorite_game, "
            "favorite_number or current_goal. Values can be text, numbers, "
            "true/false, lists or JSON objects."
        )
        description.setObjectName("cardDescription")
        description.setWordWrap(True)
        card_layout.addWidget(description)

        self.custom_table = QTableWidget(0, 2)
        self.custom_table.setObjectName("customFactsTable")
        self.custom_table.setHorizontalHeaderLabels(["Fact name", "Value"])
        self.custom_table.verticalHeader().setVisible(False)
        self.custom_table.setAlternatingRowColors(False)
        self.custom_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.custom_table.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.custom_table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.SelectedClicked
        )
        self.custom_table.setMinimumHeight(175)
        header = self.custom_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.custom_table.itemChanged.connect(self._mark_profile_dirty)
        card_layout.addWidget(self.custom_table)

        actions = QHBoxLayout()
        actions.setSpacing(9)

        add_button = QPushButton("＋ Add fact")
        add_button.setObjectName("actionButton")
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self._add_custom_fact)
        actions.addWidget(add_button)

        remove_button = QPushButton("Remove selected")
        remove_button.setObjectName("actionButton")
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.clicked.connect(self._remove_selected_custom_facts)
        actions.addWidget(remove_button)

        actions.addStretch(1)

        raw_button = QPushButton("Open raw JSON")
        raw_button.setObjectName("actionButton")
        raw_button.setCursor(Qt.CursorShape.PointingHandCursor)
        raw_button.clicked.connect(
            lambda: self.open_file(self.project_root() / "user_profile.json")
        )
        actions.addWidget(raw_button)

        card_layout.addLayout(actions)
        return card

    def _load_profile_into_form(self) -> None:
        profile_path = self.project_root() / "user_profile.json"
        store = UserProfile(profile_path)

        try:
            profile = store.load()
        except ValueError as error:
            self._set_profile_status(str(error), "error")
            return

        if not profile:
            profile = {
                "_instructions": (
                    "Edit these values in MV.ai's Profile settings. Do not "
                    "store passwords, API keys, bank details or secrets here."
                ),
                "personal": {},
                "education": {},
                "preferences": {},
                "projects": {},
                "devices": {},
                "custom": {},
            }

        self._profile_data = profile
        self._loading_profile = True

        try:
            for (section, key), field in self._profile_inputs.items():
                section_data = profile.get(section, {})
                value = (
                    section_data.get(key)
                    if isinstance(section_data, dict)
                    else None
                )
                field.setText("" if value is None else str(value))

            table = self.custom_table
            if table is not None:
                table.blockSignals(True)
                table.setRowCount(0)
                custom = profile.get("custom", {})
                if isinstance(custom, dict):
                    for key, value in custom.items():
                        self._append_custom_row(
                            str(key),
                            self._profile_value_to_text(value),
                        )
                table.blockSignals(False)
        finally:
            self._loading_profile = False

        self._profile_dirty = False
        status = store.get_status()
        fact_count = status.get("fact_count", 0)
        self._set_profile_status(
            f"Profile loaded • {fact_count} saved facts",
            "success",
        )

    def _save_profile_from_form(self) -> None:
        profile_path = self.project_root() / "user_profile.json"
        store = UserProfile(profile_path)

        try:
            profile = self._collect_profile_from_form()
            store.save(profile)
        except ValueError as error:
            self._set_profile_status(str(error), "error")
            return

        self._profile_data = profile
        self._profile_dirty = False
        fact_count = store.get_status().get("fact_count", 0)
        self._set_profile_status(
            f"Saved successfully • {fact_count} facts are ready for MV.ai",
            "success",
        )

    def _collect_profile_from_form(self) -> dict[str, Any]:
        # JSON round-tripping gives us a safe deep copy while preserving all
        # unknown top-level sections and fields that the visual form does not
        # currently expose.
        profile = json.loads(json.dumps(self._profile_data or {}))
        profile.setdefault(
            "_instructions",
            "Edit these values in MV.ai's Profile settings. Do not store secrets.",
        )

        for (section, key), field in self._profile_inputs.items():
            section_data = profile.get(section)
            if not isinstance(section_data, dict):
                section_data = {}
                profile[section] = section_data

            text = field.text().strip()
            if section == "personal" and key == "age":
                if not text:
                    section_data[key] = None
                else:
                    age = int(text)
                    if not 0 <= age <= 130:
                        raise ValueError("Age must be between 0 and 130.")
                    section_data[key] = age
            else:
                section_data[key] = text

        custom: dict[str, Any] = {}
        seen_keys: set[str] = set()
        table = self.custom_table
        if table is not None:
            for row in range(table.rowCount()):
                key_item = table.item(row, 0)
                value_item = table.item(row, 1)
                key = key_item.text().strip() if key_item else ""
                value_text = value_item.text().strip() if value_item else ""

                if not key and not value_text:
                    continue
                if not key:
                    raise ValueError(
                        f"Custom fact row {row + 1} needs a fact name."
                    )
                if key.startswith("_"):
                    raise ValueError(
                        "Custom fact names cannot begin with an underscore."
                    )
                if len(key) > 80:
                    raise ValueError(
                        f"Custom fact '{key[:30]}…' is too long."
                    )

                normalized_key = key.casefold()
                if normalized_key in seen_keys:
                    raise ValueError(
                        f"Custom fact '{key}' appears more than once."
                    )
                seen_keys.add(normalized_key)
                custom[key] = self._parse_custom_value(value_text)

        profile["custom"] = custom
        return profile

    def _add_custom_fact(self) -> None:
        table = self.custom_table
        if table is None:
            return

        row = table.rowCount()
        self._append_custom_row("", "")
        table.setCurrentCell(row, 0)
        table.editItem(table.item(row, 0))
        self._mark_profile_dirty()

    def _append_custom_row(self, key: str, value: str) -> None:
        table = self.custom_table
        if table is None:
            return

        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QTableWidgetItem(key))
        table.setItem(row, 1, QTableWidgetItem(value))

    def _remove_selected_custom_facts(self) -> None:
        table = self.custom_table
        if table is None:
            return

        selected_rows = sorted(
            {index.row() for index in table.selectionModel().selectedRows()},
            reverse=True,
        )
        if not selected_rows:
            self._set_profile_status(
                "Select one or more custom-fact rows to remove.",
                "warning",
            )
            return

        for row in selected_rows:
            table.removeRow(row)
        self._mark_profile_dirty()

    def _mark_profile_dirty(self, *_args) -> None:
        if self._loading_profile:
            return
        self._profile_dirty = True
        self._set_profile_status(
            "Unsaved changes • press Save profile when finished",
            "warning",
        )

    def _set_profile_status(self, message: str, state: str) -> None:
        label = self.profile_status
        if label is None:
            return

        label.setText(message)
        label.setProperty("statusState", state)
        label.style().unpolish(label)
        label.style().polish(label)
        label.update()

    @staticmethod
    def _profile_value_to_text(value: Any) -> str:
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return str(value)

    @staticmethod
    def _parse_custom_value(text: str) -> Any:
        stripped = text.strip()
        if not stripped:
            return ""

        lowered = stripped.lower()
        looks_like_json = (
            lowered in {"true", "false", "null"}
            or stripped.startswith("[")
            or stripped.startswith("{")
            or stripped.startswith('"')
            or stripped[0].isdigit()
            or stripped[0] in {"-", "+"}
        )
        if looks_like_json:
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass
        return stripped

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

            QLabel#profileIntro {
                color: #AEB5C5;
                font-size: 11px;
                padding: 1px 3px 4px 3px;
            }

            QLabel#profileFieldLabel {
                color: #C7CDDA;
                font-size: 11px;
                min-width: 118px;
            }

            QLineEdit#profileInput {
                background: #0F1320;
                color: #F1F3F8;
                border: 1px solid #30384D;
                border-radius: 10px;
                padding: 9px 11px;
                selection-background-color: #6F61F6;
            }

            QLineEdit#profileInput:hover {
                border-color: #46516D;
            }

            QLineEdit#profileInput:focus {
                border: 1px solid #7469DC;
                background: #121725;
            }

            QLineEdit#profileInput::placeholder {
                color: #626B80;
            }

            QTableWidget#customFactsTable {
                background: #0F1320;
                alternate-background-color: #121725;
                color: #E9ECF4;
                border: 1px solid #30384D;
                border-radius: 11px;
                gridline-color: #252C3D;
                selection-background-color: #38345F;
                selection-color: #FFFFFF;
                outline: none;
            }

            QTableWidget#customFactsTable::item {
                padding: 7px;
                border: none;
            }

            QHeaderView::section {
                background: #171C29;
                color: #AEB5C5;
                border: none;
                border-bottom: 1px solid #30384D;
                padding: 8px;
                font-size: 10px;
                font-weight: 650;
            }

            QLabel#profileWarning {
                background: #211A20;
                color: #D8A9B4;
                border: 1px solid #4C303A;
                border-radius: 12px;
                padding: 11px 13px;
                font-size: 10px;
            }

            QFrame#profileFooter {
                background: #141927;
                border: 1px solid #30384D;
                border-radius: 14px;
            }

            QLabel#profileStatus {
                color: #9EA7BA;
                font-size: 10px;
            }

            QLabel#profileStatus[statusState="success"] {
                color: #78DCA7;
            }

            QLabel#profileStatus[statusState="warning"] {
                color: #E3C277;
            }

            QLabel#profileStatus[statusState="error"] {
                color: #FF8E9B;
            }

            QPushButton#secondaryButton,
            QPushButton#saveProfileButton {
                border-radius: 10px;
                padding: 9px 14px;
                font-size: 11px;
                font-weight: 650;
            }

            QPushButton#secondaryButton {
                background: #1C2232;
                color: #E7EAF2;
                border: 1px solid #38415A;
            }

            QPushButton#secondaryButton:hover {
                background: #292F46;
                border-color: #5A6683;
            }

            QPushButton#saveProfileButton {
                background: #6F61F6;
                color: #FFFFFF;
                border: 1px solid #8C82FF;
            }

            QPushButton#saveProfileButton:hover {
                background: #7D70FF;
                border-color: #A29AFF;
            }
        """
