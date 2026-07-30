from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from memory.memory_manager import MemoryManager
from memory.memory_policy import MemoryPolicy, SensitiveMemoryError


class MemoryEditorDialog(QDialog):
    """Small editor for creating or changing one long-term memory."""

    CATEGORIES = (
        "general",
        "personal",
        "preference",
        "project",
        "folder",
        "application",
        "routine",
        "device",
    )

    def __init__(
        self,
        parent=None,
        memory: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.memory = memory or {}
        self.result_data: dict[str, Any] | None = None

        self.setWindowTitle("Edit memory" if memory else "Add memory")
        self.setModal(True)
        self.setMinimumWidth(520)
        self.setObjectName("memoryEditorDialog")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 20, 22, 20)
        root.setSpacing(14)

        title = QLabel("Edit long-term memory" if memory else "Add long-term memory")
        title.setObjectName("memoryEditorTitle")
        root.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.category_input = QComboBox()
        self.category_input.setObjectName("memoryCombo")
        self.category_input.setEditable(True)
        self.category_input.addItems(self.CATEGORIES)

        self.key_input = QLineEdit()
        self.key_input.setObjectName("memoryInput")
        self.key_input.setPlaceholderText("preferred_coding_folder")

        self.value_input = QTextEdit()
        self.value_input.setObjectName("memoryValueInput")
        self.value_input.setPlaceholderText("Desktop/MV.ai_V4")
        self.value_input.setMinimumHeight(100)

        self.importance_input = QSpinBox()
        self.importance_input.setObjectName("memorySpin")
        self.importance_input.setRange(1, 10)
        self.importance_input.setValue(5)

        form.addRow("Category", self.category_input)
        form.addRow("Memory key", self.key_input)
        form.addRow("Value", self.value_input)
        form.addRow("Importance", self.importance_input)
        root.addLayout(form)

        warning = QLabel(
            "Do not store passwords, API keys, OTPs, banking information, "
            "private keys, or exact home addresses."
        )
        warning.setObjectName("memoryEditorWarning")
        warning.setWordWrap(True)
        root.addWidget(warning)

        self.error_label = QLabel("")
        self.error_label.setObjectName("memoryEditorError")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        root.addWidget(self.error_label)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("secondaryButton")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save memory")
        save.setObjectName("saveProfileButton")
        save.clicked.connect(self._accept_if_valid)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        root.addLayout(buttons)

        if memory:
            self.category_input.setCurrentText(str(memory.get("category", "general")))
            self.key_input.setText(str(memory.get("memory_key", "")))
            self.value_input.setPlainText(str(memory.get("memory_value", "")))
            self.importance_input.setValue(int(memory.get("importance", 5)))

        self.setStyleSheet(self._stylesheet())

    def _accept_if_valid(self) -> None:
        category = self.category_input.currentText().strip().lower().replace(" ", "_")
        key = self.key_input.text().strip()
        value = self.value_input.toPlainText().strip()

        if not key:
            self._show_error("Memory key cannot be empty.")
            return
        if not value:
            self._show_error("Memory value cannot be empty.")
            return
        if not category:
            category = "general"

        try:
            MemoryPolicy.validate(key, value)
        except SensitiveMemoryError as error:
            self._show_error(str(error))
            return

        self.result_data = {
            "category": category,
            "key": key,
            "value": value,
            "importance": self.importance_input.value(),
        }
        self.accept()

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()

    @staticmethod
    def _stylesheet() -> str:
        return """
            QDialog#memoryEditorDialog {
                background: #10131C;
                color: #F5F7FB;
            }
            QLabel { color: #DCE1EC; }
            QLabel#memoryEditorTitle {
                color: #F7F8FC;
                font-size: 18px;
                font-weight: 750;
            }
            QLabel#memoryEditorWarning {
                background: #211A20;
                color: #D8A9B4;
                border: 1px solid #4C303A;
                border-radius: 10px;
                padding: 10px;
            }
            QLabel#memoryEditorError { color: #FF8E9B; }
            QLineEdit#memoryInput, QTextEdit#memoryValueInput,
            QComboBox#memoryCombo, QSpinBox#memorySpin {
                background: #0F1320;
                color: #F1F3F8;
                border: 1px solid #30384D;
                border-radius: 9px;
                padding: 8px 10px;
                selection-background-color: #6F61F6;
            }
            QComboBox#memoryCombo QAbstractItemView {
                background: #151927;
                color: #F1F3F8;
                selection-background-color: #38345F;
            }
            QPushButton#secondaryButton, QPushButton#saveProfileButton {
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 650;
            }
            QPushButton#secondaryButton {
                background: #1C2232;
                color: #E7EAF2;
                border: 1px solid #38415A;
            }
            QPushButton#saveProfileButton {
                background: #6F61F6;
                color: white;
                border: 1px solid #8C82FF;
            }
        """


class MemorySettingsPage(QWidget):
    """Searchable Memory tab embedded in the More popup."""

    def __init__(
        self,
        memory_manager: MemoryManager | None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.memory_manager = memory_manager
        self.setObjectName("memoryPage")

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 4, 0)
        root.setSpacing(12)

        intro = QLabel(
            "Memories learned through explicit commands live here. Your editable "
            "profile remains separate in user_profile.json."
        )
        intro.setObjectName("profileIntro")
        intro.setWordWrap(True)
        root.addWidget(intro)

        toolbar = QFrame()
        toolbar.setObjectName("memoryToolbar")
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(12, 10, 12, 10)
        toolbar_layout.setSpacing(8)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("memorySearch")
        self.search_input.setPlaceholderText("Search memories by topic, key, or value...")
        self.search_input.textChanged.connect(self.refresh)
        toolbar_layout.addWidget(self.search_input, 1)

        self.category_filter = QComboBox()
        self.category_filter.setObjectName("memoryFilter")
        self.category_filter.addItem("All categories", "")
        for category in MemoryEditorDialog.CATEGORIES:
            self.category_filter.addItem(category.replace("_", " ").title(), category)
        self.category_filter.currentIndexChanged.connect(self.refresh)
        toolbar_layout.addWidget(self.category_filter)

        add_button = QPushButton("＋ Add")
        add_button.setObjectName("saveProfileButton")
        add_button.clicked.connect(self.add_memory)
        toolbar_layout.addWidget(add_button)
        root.addWidget(toolbar)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("memoryTable")
        self.table.setHorizontalHeaderLabels(
            ["Category", "Memory", "Value", "Importance", "Updated"]
        )
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().resizeSection(0, 100)
        self.table.horizontalHeader().resizeSection(1, 165)
        self.table.horizontalHeader().resizeSection(2, 300)
        self.table.horizontalHeader().resizeSection(3, 78)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.doubleClicked.connect(self.edit_selected)
        root.addWidget(self.table, 1)

        footer = QFrame()
        footer.setObjectName("profileFooter")
        footer_layout = QHBoxLayout(footer)
        footer_layout.setContentsMargins(12, 9, 12, 9)
        self.status = QLabel("")
        self.status.setObjectName("profileStatus")
        footer_layout.addWidget(self.status, 1)

        refresh_button = QPushButton("Refresh")
        refresh_button.setObjectName("secondaryButton")
        refresh_button.clicked.connect(self.refresh)
        edit_button = QPushButton("Edit selected")
        edit_button.setObjectName("secondaryButton")
        edit_button.clicked.connect(self.edit_selected)
        forget_button = QPushButton("Forget selected")
        forget_button.setObjectName("dangerButton")
        forget_button.clicked.connect(self.forget_selected)
        footer_layout.addWidget(refresh_button)
        footer_layout.addWidget(edit_button)
        footer_layout.addWidget(forget_button)
        root.addWidget(footer)

        self.refresh()

    def refresh(self, *args) -> None:
        if self.memory_manager is None:
            self.table.setRowCount(0)
            self.status.setText("Memory manager is unavailable.")
            return

        query = self.search_input.text().strip()
        category = self.category_filter.currentData() or None
        try:
            if query:
                memories = self.memory_manager.search_relevant(
                    query,
                    category=category,
                    limit=100,
                    minimum_score=0.12,
                )
            else:
                memories = self.memory_manager.get_all_memories(
                    category=category,
                    limit=200,
                )
        except Exception as error:
            self.status.setText(f"Could not load memories: {error}")
            return

        self.table.setRowCount(len(memories))
        for row, memory in enumerate(memories):
            values = (
                str(memory.get("category", "general")),
                MemoryManager.display_key(str(memory.get("memory_key", ""))),
                str(memory.get("memory_value", "")),
                str(memory.get("importance", 5)),
                str(memory.get("updated_at", "")).replace("T", " "),
            )
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, int(memory["id"]))
                self.table.setItem(row, column, item)

        noun = "memory" if len(memories) == 1 else "memories"
        self.status.setText(f"{len(memories)} active {noun}")

    def _selected_memory(self) -> dict[str, Any] | None:
        if self.memory_manager is None:
            return None
        row = self.table.currentRow()
        if row < 0:
            self.status.setText("Select a memory first.")
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        memory_id = item.data(Qt.ItemDataRole.UserRole)
        return self.memory_manager.get_memory_by_id(int(memory_id))

    def add_memory(self) -> None:
        if self.memory_manager is None:
            return
        dialog = MemoryEditorDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_data:
            return
        data = dialog.result_data
        try:
            self.memory_manager.create_memory(
                key=data["key"],
                value=data["value"],
                category=data["category"],
                importance=data["importance"],
                source="memory_tab",
            )
        except Exception as error:
            QMessageBox.warning(self, "Could not save memory", str(error))
            return
        self.refresh()
        self.status.setText("Memory saved.")

    def edit_selected(self, *args) -> None:
        memory = self._selected_memory()
        if memory is None or self.memory_manager is None:
            return
        dialog = MemoryEditorDialog(self, memory)
        if dialog.exec() != QDialog.DialogCode.Accepted or not dialog.result_data:
            return
        data = dialog.result_data
        try:
            self.memory_manager.update_memory(
                memory["id"],
                key=data["key"],
                value=data["value"],
                category=data["category"],
                importance=data["importance"],
                source="memory_tab",
            )
        except Exception as error:
            QMessageBox.warning(self, "Could not update memory", str(error))
            return
        self.refresh()
        self.status.setText("Memory updated.")

    def forget_selected(self) -> None:
        memory = self._selected_memory()
        if memory is None or self.memory_manager is None:
            return
        key = MemoryManager.display_key(memory["memory_key"])
        answer = QMessageBox.question(
            self,
            "Forget memory",
            f"Forget this memory?\n\n[{memory['category']}] {key}: "
            f"{memory['memory_value']}\n\nIt will be deactivated, not permanently erased.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.memory_manager.forget_by_id(memory["id"], permanent=False)
        self.refresh()
        self.status.setText("Memory forgotten.")
