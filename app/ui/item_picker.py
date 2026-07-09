"""The catalogue of conjuring — search, filter by category and rarity, and
summon any item in the game into the bag."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QVBoxLayout)

from ..core import items
from . import icons, theme, widgets

RARITY_FILTERS = [("Any rarity", 0), ("Uncommon+", 3), ("Rare+", 4),
                  ("Epic+", 5), ("Legendary", 6)]


class ItemPicker(QDialog):
    conjure = Signal(str, int)   # item_data, count

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Conjure an item")
        self.setModal(True)
        self.setMinimumSize(560, 620)
        self.setStyleSheet(f"QDialog {{ background: {theme.BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        title = QLabel("Conjure an item")
        title.setStyleSheet(
            f"font-family: '{theme.display_family()}'; font-size: 20px;"
            f"font-weight: 650; color: {theme.GOLD_TEXT};")
        root.addWidget(title)
        sub = QLabel("Every item in the wilds. It appears in the first free bag "
                     "slot — a checkpoint is taken first.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        root.addWidget(sub)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search 788 items…")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(34)
        self.search.textChanged.connect(self._refresh)
        filters.addWidget(self.search, 1)
        self.cat_combo = QComboBox()
        self.cat_combo.setFixedHeight(34)
        self.cat_combo.addItem("All categories", "")
        for c in items.categories():
            self.cat_combo.addItem(c, c)
        self.cat_combo.currentIndexChanged.connect(self._refresh)
        filters.addWidget(self.cat_combo)
        self.rarity_combo = QComboBox()
        self.rarity_combo.setFixedHeight(34)
        for label, rank in RARITY_FILTERS:
            self.rarity_combo.addItem(label, rank)
        self.rarity_combo.currentIndexChanged.connect(self._refresh)
        filters.addWidget(self.rarity_combo)
        root.addLayout(filters)

        self.count_label = QLabel("")
        self.count_label.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;")
        root.addWidget(self.count_label)

        self.list = QListWidget()
        self.list.setIconSize(QSize(20, 20))
        self.list.setStyleSheet(f"""
            QListWidget {{ background: {theme.FIELD_BG}; border: 1px solid {theme.BORDER};
                border-radius: 10px; padding: 4px; outline: none; }}
            QListWidget::item {{ padding: 7px 8px; border-radius: 7px; }}
            QListWidget::item:selected {{ background: {theme.SURFACE_2}; }}
            QListWidget::item:hover {{ background: rgba(232,162,61,0.08); }}""")
        self.list.itemSelectionChanged.connect(self._on_select)
        self.list.itemDoubleClicked.connect(lambda _: self._conjure())
        root.addWidget(self.list, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.sel_label = QLabel("Pick an item")
        self.sel_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        footer.addWidget(self.sel_label, 1)
        qty = QLabel("Qty")
        qty.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        footer.addWidget(qty)
        from PySide6.QtGui import QIntValidator
        self.qty = QLineEdit("1")
        self.qty.setValidator(QIntValidator(1, 9999))
        self.qty.setFixedSize(66, 32)
        footer.addWidget(self.qty)
        self.max_chip = widgets.make_button("Max", "chip", height=26)
        self.max_chip.clicked.connect(self._set_max)
        footer.addWidget(self.max_chip)
        cancel = widgets.make_button("Cancel", "ghost", height=34)
        cancel.clicked.connect(self.reject)
        self.conjure_btn = widgets.make_button("Conjure", "ember", height=34)
        self.conjure_btn.setMinimumWidth(110)
        self.conjure_btn.setEnabled(False)
        self.conjure_btn.clicked.connect(self._conjure)
        footer.addWidget(cancel)
        footer.addWidget(self.conjure_btn)
        root.addLayout(footer)

        self._refresh()
        self.search.setFocus()

    def _refresh(self):
        query = self.search.text()
        category = self.cat_combo.currentData()
        min_rank = self.rarity_combo.currentData()
        rows = items.search(query, category, min_rank)
        self.list.clear()
        for row in rows[:400]:
            label, color = items.RARITY.get(row["rank"], items.RARITY[1])
            item = QListWidgetItem(icons.icon(items.CATEGORY_ICON.get(
                row["category"], "gem"), color, 18), row["name"])
            item.setForeground(_qcolor(color))
            item.setData(Qt.UserRole, row)
            item.setToolTip(f"{label} · {row['category']} · stacks to {row['max']}")
            self.list.addItem(item)
        shown = min(len(rows), 400)
        more = f"  (showing first 400 — refine to see the rest)" if len(rows) > 400 else ""
        self.count_label.setText(f"{len(rows)} item{'s' if len(rows) != 1 else ''} match"
                                 f"{more}")

    def _on_select(self):
        row = self._selected_row()
        if not row:
            self.conjure_btn.setEnabled(False)
            self.sel_label.setText("Pick an item")
            return
        label, color = items.RARITY.get(row["rank"], items.RARITY[1])
        self.sel_label.setText(
            f"<b>{row['name']}</b> · <span style='color:{color}'>{label}</span> · "
            f"stacks to {row['max']}")
        self.conjure_btn.setEnabled(True)
        if row["max"] <= 1:
            self.qty.setText("1")
            self.qty.setEnabled(False)
        else:
            self.qty.setEnabled(True)

    def _selected_row(self):
        item = self.list.currentItem()
        return item.data(Qt.UserRole) if item else None

    def _set_max(self):
        row = self._selected_row()
        if row:
            self.qty.setText(str(row["max"]))

    def _conjure(self):
        row = self._selected_row()
        if not row:
            return
        count = int(self.qty.text()) if self.qty.text().strip() else 1
        count = max(1, min(count, row["max"]))
        self.conjure.emit(row["id"], count)
        self.accept()


def _qcolor(hex_str):
    from PySide6.QtGui import QColor
    return QColor(hex_str)
