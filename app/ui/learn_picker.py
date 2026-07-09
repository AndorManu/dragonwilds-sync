"""Browse and unlock specific spells, recipes, and buildings. Multi-select so
you can tick several and learn them in one go (one checkpoint)."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QComboBox, QDialog, QHBoxLayout, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem,
                               QVBoxLayout)

from ..core import items, learn
from . import icons, theme, widgets

RARITY_FILTERS = [("Any rarity", 0), ("Uncommon+", 3), ("Rare+", 4),
                  ("Epic+", 5), ("Legendary", 6)]


class LearnPicker(QDialog):
    learn_selected = Signal(str, list)   # kind, [ids]

    def __init__(self, owned_by_kind: dict, parent=None):
        super().__init__(parent)
        self._owned = owned_by_kind or {}
        self._kind = "recipes"
        self.setWindowTitle("Learn")
        self.setModal(True)
        self.setMinimumSize(580, 640)
        self.setStyleSheet(f"QDialog {{ background: {theme.BG}; }}")

        root = QVBoxLayout(self)
        root.setContentsMargins(22, 18, 22, 18)
        root.setSpacing(12)

        title = QLabel("Learn what you like")
        title.setStyleSheet(
            f"font-family: '{theme.display_family()}'; font-size: 20px;"
            f"font-weight: 650; color: {theme.GOLD_TEXT};")
        root.addWidget(title)
        sub = QLabel("Tick anything and learn it. Recipes show what they craft. "
                     "A checkpoint is taken before the change.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        root.addWidget(sub)

        kind_row = QHBoxLayout()
        kind_row.setSpacing(8)
        self._kind_chips = {}
        for kind, label in (("recipes", "Recipes"), ("spells", "Spells"),
                            ("buildings", "Buildings")):
            chip = widgets.make_button(f"{label}  ({learn.total(kind)})",
                                       "chip", height=30)
            chip.setCheckable(True)
            chip.clicked.connect(lambda _=False, k=kind: self._set_kind(k))
            self._kind_chips[kind] = chip
            kind_row.addWidget(chip)
        kind_row.addStretch(1)
        root.addLayout(kind_row)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search = QLineEdit()
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(34)
        self.search.textChanged.connect(self._refresh)
        filters.addWidget(self.search, 1)
        self.cat_combo = QComboBox()
        self.cat_combo.setFixedHeight(34)
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
        self.list.setSelectionMode(QListWidget.ExtendedSelection)
        self.list.setStyleSheet(f"""
            QListWidget {{ background: {theme.FIELD_BG}; border: 1px solid {theme.BORDER};
                border-radius: 10px; padding: 4px; outline: none; }}
            QListWidget::item {{ padding: 7px 8px; border-radius: 7px; }}
            QListWidget::item:selected {{ background: {theme.SURFACE_2}; }}
            QListWidget::item:hover {{ background: rgba(232,162,61,0.08); }}""")
        self.list.itemSelectionChanged.connect(self._on_select)
        root.addWidget(self.list, 1)

        footer = QHBoxLayout()
        footer.setSpacing(8)
        self.sel_label = QLabel("Nothing selected")
        self.sel_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        footer.addWidget(self.sel_label, 1)
        close = widgets.make_button("Done", "ghost", height=34)
        close.clicked.connect(self.accept)
        self.learn_btn = widgets.make_button("Learn", "ember", height=34)
        self.learn_btn.setMinimumWidth(130)
        self.learn_btn.setEnabled(False)
        self.learn_btn.clicked.connect(self._learn)
        footer.addWidget(close)
        footer.addWidget(self.learn_btn)
        root.addLayout(footer)

        self._set_kind("recipes")
        self.search.setFocus()

    def _set_kind(self, kind):
        self._kind = kind
        for k, chip in self._kind_chips.items():
            chip.setChecked(k == kind)
        recipes = kind == "recipes"
        self.cat_combo.setVisible(recipes)
        self.rarity_combo.setVisible(recipes)
        self.search.setPlaceholderText(f"Search {learn.total(kind)} {kind}…")
        if recipes:
            self.cat_combo.blockSignals(True)
            self.cat_combo.clear()
            self.cat_combo.addItem("All categories", "")
            for c in learn.recipe_categories():
                self.cat_combo.addItem(c, c)
            self.cat_combo.blockSignals(False)
        self._refresh()

    def _refresh(self):
        owned = set(self._owned.get(self._kind, ()))
        rows = learn.search(
            self._kind, self.search.text(),
            self.cat_combo.currentData() if self._kind == "recipes" else "",
            self.rarity_combo.currentData() if self._kind == "recipes" else 0,
            owned)
        self.list.clear()
        for row in rows[:500]:
            text = row["name"] + ("   ✓ known" if row["owned"] else "")
            item = QListWidgetItem(icons.icon(row["icon"], row["color"], 18), text)
            item.setData(Qt.UserRole, row)
            if row["owned"]:
                item.setForeground(QColor(theme.TEXT_FAINT))
                item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            else:
                item.setForeground(QColor(row["color"]))
            item.setToolTip(row["sub"])
            self.list.addItem(item)
        learnable = sum(1 for r in rows if not r["owned"])
        more = "  (first 500 shown)" if len(rows) > 500 else ""
        self.count_label.setText(f"{len(rows)} match · {learnable} not yet known{more}")

    def _on_select(self):
        rows = [i.data(Qt.UserRole) for i in self.list.selectedItems()]
        rows = [r for r in rows if not r["owned"]]
        n = len(rows)
        self.learn_btn.setEnabled(n > 0)
        self.learn_btn.setText(f"Learn {n}" if n else "Learn")
        if n == 1:
            self.sel_label.setText(f"<b>{rows[0]['name']}</b> · {rows[0]['sub']}")
        elif n:
            self.sel_label.setText(f"{n} selected")
        else:
            self.sel_label.setText("Nothing selected")

    def _learn(self):
        ids = [i.data(Qt.UserRole)["id"] for i in self.list.selectedItems()
               if not i.data(Qt.UserRole)["owned"]]
        if ids:
            self.learn_selected.emit(self._kind, ids)
