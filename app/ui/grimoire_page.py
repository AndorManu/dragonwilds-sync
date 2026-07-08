"""The Dragon's Bargain — the hidden save editor. Found, not advertised.

Power, for a price paid in honesty: every bargain checkpoints the old self
first, refuses to work while the game runs, and touches only the numbers
you ask it to. Dressed for the occasion: a slowly-turning arcane seal,
drifting embers, and each skill under its own emblem.
"""

import math
import random

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QIntValidator, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout,
                               QLabel, QLineEdit, QScrollArea, QVBoxLayout,
                               QWidget)

from ..core import levels
from ..core.characters import SKILL_NAME_CHOICES, EditPlan, skill_label
from . import icons, theme, widgets

EMBER_COUNT = 10


class SkillMedallion(QFrame):
    """A small ember-ringed circle holding the skill's emblem."""

    def __init__(self, icon_name, size=34, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.setStyleSheet(
            f"SkillMedallion {{ background: rgba(232,162,61,0.10);"
            f"border: 1px solid rgba(232,162,61,0.35);"
            f"border-radius: {size // 2}px; }}")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        icon = QLabel()
        icon.setPixmap(icons.pixmap(icon_name, theme.EMBER_HI, int(size * 0.55)))
        icon.setAlignment(Qt.AlignCenter)
        icon.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(icon)


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
        self._skill_edits = {}      # skill_id -> (level_combo, xp_edit)
        self._ritual_pending = False

        # arcane backdrop state
        self._angle = 0.0
        self._embers = [{"x": random.random(), "y": random.random(),
                         "speed": 0.0012 + random.random() * 0.0025,
                         "size": 1.0 + random.random() * 1.8,
                         "phase": random.random() * 6.28}
                        for _ in range(EMBER_COUNT)]
        self._anim = QTimer(self)
        self._anim.setInterval(50)
        self._anim.timeout.connect(self._tick)

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
            f"font-weight: 650; color: {theme.GOLD_TEXT}; background: transparent;")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(4)

        flavor = QLabel("“Everything has a price. Yours is a copy of who you were.”")
        flavor.setStyleSheet(
            f"font-family: '{theme.voice_family()}'; font-style: italic;"
            f"color: {theme.TEXT_DIM}; font-size: 13.5px; background: transparent;")
        flavor.setWordWrap(True)
        root.addWidget(flavor)
        root.addSpacing(4)

        warn = QLabel("Experimental. A checkpoint is taken before every bargain "
                      "and the game must be closed.")
        warn.setWordWrap(True)
        warn.setStyleSheet(f"color: {theme.AMBER}; font-size: 11.5px;"
                           f"background: transparent;")
        root.addWidget(warn)
        root.addSpacing(10)

        pick_row = QHBoxLayout()
        pick_row.setSpacing(10)
        pick_label = QLabel("Character")
        pick_label.setProperty("role", "fieldLabel")
        pick_label.setStyleSheet("background: transparent;")
        pick_label.setMinimumWidth(70)
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
        scroll.setStyleSheet("QScrollArea { background: transparent; }")
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        self.body_box = QVBoxLayout(body)
        self.body_box.setContentsMargins(2, 2, 10, 2)
        self.body_box.setSpacing(10)
        scroll.setWidget(body)
        scroll.viewport().setStyleSheet("background: transparent;")
        root.addWidget(scroll, 1)
        root.addSpacing(10)

        buttons = QHBoxLayout()
        self.ritual_btn = widgets.make_button("Identify ritual", "ghost",
                                              "sparkle", height=38)
        self.ritual_btn.clicked.connect(self._ritual)
        buttons.addWidget(self.ritual_btn)
        buttons.addStretch(1)
        seal = widgets.PlayButton("SEAL THE BARGAIN", variant="ember",
                                  glow_color=theme.EMBER, height=46,
                                  point_size=10.5)
        seal.setMinimumWidth(210)
        seal.clicked.connect(self._seal)
        buttons.addWidget(seal)
        root.addLayout(buttons)

    # -- arcane backdrop --------------------------------------------------------
    def showEvent(self, e):
        self._anim.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def _tick(self):
        self._angle = (self._angle + 0.15) % 360
        for em in self._embers:
            em["y"] -= em["speed"]
            em["x"] += math.sin(self._angle * 0.12 + em["phase"]) * 0.0008
            if em["y"] < -0.03:
                em["y"] = 1.03
                em["x"] = random.random()
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        cx, cy = w * 0.5, h * 0.46

        # the turning seal: two rings, tick marks, wandering diamonds
        gold = QColor(theme.EMBER)
        gold.setAlphaF(0.07)
        pen = QPen(gold, 1.2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        r_outer, r_inner = w * 0.52, w * 0.40
        p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
        p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        for i in range(24):
            a = math.radians(self._angle + i * 15)
            x1 = cx + math.cos(a) * r_inner
            y1 = cy + math.sin(a) * r_inner
            x2 = cx + math.cos(a) * (r_inner + 8)
            y2 = cy + math.sin(a) * (r_inner + 8)
            p.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        diamond = QColor(theme.EMBER)
        diamond.setAlphaF(0.12)
        p.setBrush(QBrush(diamond))
        p.setPen(Qt.NoPen)
        for i in range(4):
            a = math.radians(-self._angle * 0.6 + i * 90)
            x = cx + math.cos(a) * r_outer
            y = cy + math.sin(a) * r_outer
            p.save()
            p.translate(x, y)
            p.rotate(45)
            p.drawRect(-3, -3, 6, 6)
            p.restore()

        # drifting embers
        ember = QColor(theme.EMBER_HI)
        for em in self._embers:
            a = 0.10 + 0.10 * math.sin(self._angle * 0.1 + em["phase"])
            ember.setAlphaF(max(0.0, a))
            p.setBrush(QBrush(ember))
            p.drawEllipse(QPointF(em["x"] * w, em["y"] * h),
                          em["size"], em["size"])
        p.end()

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
        self.ritual_btn.setText("Finish ritual" if self._ritual_pending
                                else "Identify ritual")
        self._render_skills()

    def _current_info(self):
        i = self.char_combo.currentIndex()
        return self._infos[i] if 0 <= i < len(self._infos) else None

    def skill_label(self, skill_id, index):
        return skill_label(skill_id, index, self._labels)

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
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; padding: 20px;"
                                f"background: transparent;")
            empty.setAlignment(Qt.AlignCenter)
            self.body_box.addWidget(empty)
            self.body_box.addStretch(1)
            return

        skills_head = QLabel("SKILLS — PICK A NEW LEVEL")
        skills_head.setObjectName("SettingsSection")
        skills_head.setStyleSheet("background: transparent;")
        self.body_box.addWidget(skills_head)

        card = QFrame()
        card.setObjectName("GlassCard")
        grid = QVBoxLayout(card)
        grid.setContentsMargins(12, 6, 12, 6)
        grid.setSpacing(0)
        rows = sorted(enumerate(info.skills),
                      key=lambda t: self.skill_label(t[1]["Id"], t[0]).lower())
        for i, skill in rows:
            grid.addWidget(self._skill_row(skill, i, first=(grid.count() == 0)))
        self.body_box.addWidget(card)

        boons_head = QLabel("QUICK BOONS")
        boons_head.setObjectName("SettingsSection")
        boons_head.setStyleSheet("background: transparent;")
        self.body_box.addWidget(boons_head)
        self.heal_check = QCheckBox("Restore vitals — health, stamina, food, water")
        self.repair_check = QCheckBox("Repair everything carried and worn")
        for c in (self.heal_check, self.repair_check):
            c.setStyleSheet("background: transparent;")
            self.body_box.addWidget(c)

        hint = QLabel("Levels use the game's own table (wiki-verified, Lv 1–99; "
                      "the road past 93 gets steep). The tiny xp box overrides "
                      "the level pick, for the precise-minded.")
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        hint.setStyleSheet("background: transparent;")
        self.body_box.addWidget(hint)
        self.body_box.addStretch(1)

    def _skill_row(self, skill, index, first=False):
        row = QWidget()
        row.setStyleSheet("background: transparent;" if first else
                          f"background: transparent;"
                          f"border-top: 1px solid rgba(232,162,61,0.10);")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 7, 0, 7)
        rl.setSpacing(10)

        label_text = self.skill_label(skill["Id"], index)
        rl.addWidget(SkillMedallion(icons.skill_icon_name(label_text)))

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel(label_text)
        name.setStyleSheet("border: none; background: transparent;"
                           "font-size: 13px; font-weight: 650;")
        current_xp = int(skill.get("Xp") or 0)
        current_level = levels.level_for_xp(current_xp)
        meta = QLabel(f"Lv {current_level} · {current_xp:,} xp")
        meta.setStyleSheet(f"border: none; background: transparent;"
                           f"color: {theme.TEXT_DIM}; font-size: 11.5px;")
        col.addWidget(name)
        col.addWidget(meta)
        rl.addLayout(col)
        rl.addStretch(1)

        combo = QComboBox()
        combo.setFixedSize(96, 30)
        combo.addItem("Keep", None)
        for lvl in range(2, levels.MAX_LEVEL + 1):
            mark = " ≈" if levels.is_estimated(lvl) else ""
            combo.addItem(f"Lv {lvl}{mark}", lvl)
        combo.setToolTip("Pick the level this skill should be")
        rl.addWidget(combo)

        edit = QLineEdit()
        edit.setPlaceholderText("xp")
        edit.setValidator(QIntValidator(0, 99_999_999))
        edit.setFixedSize(70, 30)
        edit.setToolTip("Exact xp (overrides the level pick)")
        rl.addWidget(edit)

        self._skill_edits[skill["Id"]] = (combo, edit)
        return row

    # -- actions ---------------------------------------------------------------
    def _seal(self):
        info = self._current_info()
        if not info:
            return
        plan = EditPlan(heal_vitals=self.heal_check.isChecked(),
                        repair_all=self.repair_check.isChecked())
        for skill_id, (combo, edit) in self._skill_edits.items():
            text = edit.text().strip()
            if text:
                plan.skill_xp[skill_id] = int(text)
                continue
            level = combo.currentData()
            if level:
                plan.skill_xp[skill_id] = levels.xp_for_level(level)
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
        choice, ok = QInputDialog.getItem(
            self, "The ritual speaks",
            f"One skill grew by {gained} xp. Which did you train?",
            SKILL_NAME_CHOICES, 0, False)
        if ok and choice:
            self.label_saved.emit(skill_id, choice)
            return True
        return False
