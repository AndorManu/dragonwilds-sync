"""The Dragon's Bargain — the hidden save editor. Found, not advertised.

Power, for a price paid in honesty: every bargain checkpoints the old self
first, refuses to work while the game runs, and touches only the numbers
you ask it to.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from ..core.characters import SKILL_NAME_CHOICES, EditPlan
from . import theme, widgets

ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII"]


class GrimoirePage(QWidget):
    back_requested = Signal()
    bargain_requested = Signal(object, object)     # char_path, EditPlan
    ritual_started = Signal(object)                # char_path
    ritual_finished = Signal()
    label_saved = Signal(str, str)                 # skill_id, label

    def __init__(self, parent=None):
        super().__init__(parent)
        self._infos = []
        self._labels = {}
        self._skill_edits = {}      # skill_id -> QLineEdit
        self._ritual_pending = False

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        title = QLabel("The Dragon's Bargain")
        title.setStyleSheet(
            f"font-family: '{theme.display_family()}'; font-size: 19px;"
            f"font-weight: 650; color: {theme.GOLD_TEXT};")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(4)

        flavor = QLabel("“Everything has a price. Yours is a copy of who you were.”")
        flavor.setStyleSheet(
            f"font-family: '{theme.voice_family()}'; font-style: italic;"
            f"color: {theme.TEXT_DIM}; font-size: 13.5px;")
        flavor.setWordWrap(True)
        root.addWidget(flavor)
        root.addSpacing(4)

        warn = QLabel("Experimental. A checkpoint is taken before every bargain and "
                      "the game must be closed. If the game refuses the changed "
                      "character, restore the checkpoint from Characters → Backups.")
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {theme.AMBER}; font-size: 11.5px;")
        root.addWidget(warn)
        root.addSpacing(10)

        pick_row = QHBoxLayout()
        pick_label = QLabel("Character")
        pick_label.setProperty("role", "fieldLabel")
        pick_row.addWidget(pick_label)
        self.char_combo = QComboBox()
        self.char_combo.setFixedHeight(34)
        self.char_combo.currentIndexChanged.connect(lambda _: self._render_skills())
        pick_row.addWidget(self.char_combo, 1)
        root.addLayout(pick_row)
        root.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self.body_box = QVBoxLayout(body)
        self.body_box.setContentsMargins(2, 2, 10, 2)
        self.body_box.setSpacing(10)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        root.addSpacing(10)

        buttons = QHBoxLayout()
        self.ritual_btn = widgets.make_button("Begin identify ritual", "ghost",
                                              "sparkle", height=38)
        self.ritual_btn.clicked.connect(self._ritual)
        buttons.addWidget(self.ritual_btn)
        buttons.addStretch(1)
        seal = widgets.make_button("Seal the bargain", "primary", height=42)
        seal.setMinimumWidth(160)
        seal.clicked.connect(self._seal)
        buttons.addWidget(seal)
        root.addLayout(buttons)

    # -- data -----------------------------------------------------------------
    def load(self, infos, labels, ritual_pending):
        self._infos = infos
        self._labels = labels or {}
        self._ritual_pending = bool(ritual_pending)
        current = self.char_combo.currentText()
        self.char_combo.blockSignals(True)
        self.char_combo.clear()
        for info in infos:
            self.char_combo.addItem(info.name)
        if current:
            self.char_combo.setCurrentText(current)
        self.char_combo.blockSignals(False)
        self.ritual_btn.setText("Finish identify ritual" if self._ritual_pending
                                else "Begin identify ritual")
        self._render_skills()

    def _current_info(self):
        i = self.char_combo.currentIndex()
        return self._infos[i] if 0 <= i < len(self._infos) else None

    def skill_label(self, skill_id, index):
        if skill_id in self._labels:
            return self._labels[skill_id]
        roman = ROMAN[index] if index < len(ROMAN) else str(index + 1)
        return f"Skill {roman}"

    # -- rendering -------------------------------------------------------------
    def _render_skills(self):
        while self.body_box.count():
            item = self.body_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._skill_edits = {}
        info = self._current_info()
        if not info:
            empty = QLabel("No characters found on this PC.")
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; padding: 20px;")
            empty.setAlignment(Qt.AlignCenter)
            self.body_box.addWidget(empty)
            self.body_box.addStretch(1)
            return

        skills_head = QLabel("SKILL EXPERIENCE")
        skills_head.setObjectName("SettingsSection")
        self.body_box.addWidget(skills_head)

        card = QFrame()
        card.setObjectName("Card")
        grid = QVBoxLayout(card)
        grid.setContentsMargins(14, 8, 14, 8)
        grid.setSpacing(0)
        for i, skill in enumerate(info.skills):
            row = QWidget()
            if i:
                row.setStyleSheet(f"border-top: 1px solid {theme.BORDER_SOFT};")
            rl = QHBoxLayout(row)
            rl.setContentsMargins(0, 7, 0, 7)
            rl.setSpacing(10)
            label = QLabel(self.skill_label(skill["Id"], i))
            label.setStyleSheet("border: none; font-size: 13px; font-weight: 600;")
            label.setMinimumWidth(120)
            rl.addWidget(label)
            current = QLabel(f"{int(skill.get('Xp') or 0):,} xp")
            current.setStyleSheet(f"border: none; color: {theme.TEXT_DIM}; font-size: 12px;")
            rl.addWidget(current)
            rl.addStretch(1)
            edit = QLineEdit()
            edit.setPlaceholderText("new xp")
            edit.setValidator(QIntValidator(0, 99_999_999))
            edit.setFixedSize(110, 30)
            self._skill_edits[skill["Id"]] = edit
            rl.addWidget(edit)
            grid.addWidget(row)
        self.body_box.addWidget(card)

        boons_head = QLabel("QUICK BOONS")
        boons_head.setObjectName("SettingsSection")
        self.body_box.addWidget(boons_head)
        self.heal_check = QCheckBox("Restore vitals — health, stamina, food, water")
        self.repair_check = QCheckBox("Repair everything carried and worn")
        self.body_box.addWidget(self.heal_check)
        self.body_box.addWidget(self.repair_check)

        ritual_hint = QLabel("Skill names are the game's secret — the ritual "
                             "uncovers them: begin it, go train exactly one skill "
                             "for a minute, quit to menu, then finish the ritual "
                             "and name what you trained.")
        ritual_hint.setWordWrap(True)
        ritual_hint.setProperty("role", "hint")
        self.body_box.addWidget(ritual_hint)
        self.body_box.addStretch(1)

    # -- actions ---------------------------------------------------------------
    def _seal(self):
        info = self._current_info()
        if not info:
            return
        plan = EditPlan(heal_vitals=self.heal_check.isChecked(),
                        repair_all=self.repair_check.isChecked())
        for skill_id, edit in self._skill_edits.items():
            text = edit.text().strip()
            if text:
                plan.skill_xp[skill_id] = int(text)
        if plan.empty():
            return
        self.bargain_requested.emit(info.path, plan)

    def _ritual(self):
        info = self._current_info()
        if not info:
            return
        if self._ritual_pending:
            self.ritual_finished.emit()
        else:
            self.ritual_started.emit(info.path)

    def offer_ritual_labels(self, gains):
        """Called by the window after finish: gains = [(skill_id, xp_gained)]."""
        from PySide6.QtWidgets import QInputDialog
        if not gains:
            return False
        skill_id, gained = gains[0]
        index = 0
        info = self._current_info()
        if info:
            for i, s in enumerate(info.skills):
                if s["Id"] == skill_id:
                    index = i
                    break
        current_guess = self.skill_label(skill_id, index)
        choice, ok = QInputDialog.getItem(
            self, "The ritual speaks",
            f"One skill grew by {gained} xp. Which did you train?",
            SKILL_NAME_CHOICES, 0, False)
        if ok and choice:
            self.label_saved.emit(skill_id, choice)
            return True
        return bool(current_guess)
