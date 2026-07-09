"""The Dragon's Bargain — the hidden save editor. Found, not advertised.

Three chambers now: Skills (level picker with living XP bars), The Bag
(a game-style inventory grid), and Scrolls (knowledge shared between
characters and friends). Dressed accordingly: a slowly-turning arcane seal,
drifting embers, and stat bars that fill when the book opens.
"""

import json
import math
import random
from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPointF, QPropertyAnimation,
                            Qt, QTimer, Signal)
from PySide6.QtGui import QBrush, QColor, QIntValidator, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout,
                               QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QScrollArea, QStackedWidget, QVBoxLayout, QWidget)

from ..core import characters, items, levels
from ..core.characters import SKILL_NAME_CHOICES, EditPlan, skill_label
from . import icons, theme, widgets

EMBER_COUNT = 10
BAG_COLUMNS = 9


class XPBar(QWidget):
    """A thin ember bar that fills to the skill's progress when shown."""

    def __init__(self, fraction: float, delay_ms: int = 0, parent=None):
        super().__init__(parent)
        self.setFixedHeight(5)
        self.setMinimumWidth(90)
        self._target = max(0.0, min(1.0, fraction))
        self._frac = 0.0
        self._anim = QPropertyAnimation(self, b"frac", self)
        self._anim.setDuration(700)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(self._target)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        QTimer.singleShot(120 + delay_ms, self._anim.start)

    def _get_frac(self):
        return self._frac

    def _set_frac(self, v):
        self._frac = v
        self.update()

    frac = Property(float, _get_frac, _set_frac)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        track = QColor(255, 255, 255, 14)
        p.setBrush(QBrush(track))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(0, 0, w, h, h / 2, h / 2)
        if self._frac > 0.01:
            grad = QLinearGradient(0, 0, w, 0)
            grad.setColorAt(0.0, QColor(theme.EMBER_DEEP))
            grad.setColorAt(1.0, QColor(theme.EMBER_HI))
            p.setBrush(QBrush(grad))
            p.drawRoundedRect(0, 0, int(w * self._frac), h, h / 2, h / 2)
            tip = QColor(theme.EMBER_HI)
            tip.setAlphaF(0.85)
            p.setBrush(QBrush(tip))
            p.drawEllipse(QPointF(w * self._frac, h / 2), h * 0.55, h * 0.55)


class SlotCell(QWidget):
    """One bag slot: category glyph tinted by rarity, count badge, durability
    sliver, name tooltip, hover glow."""

    clicked = Signal(object)   # the SlotCell itself

    def __init__(self, key, slot, edited=False, parent=None):
        super().__init__(parent)
        self.key = key
        self.slot = slot
        self._hover = False
        self._selected = False
        self._edited = edited
        self._name = items.name(slot.item_data)
        self._rarity_label, self._rarity_color = items.rarity(slot.item_data)
        self._icon = items.icon_key(slot.item_data)
        self.setFixedSize(46, 46)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        count = f"  ×{slot.count}" if slot.count is not None else ""
        dur = f"\nDurability {slot.durability}" if slot.durability is not None else ""
        cat = items.category(slot.item_data)
        self.setToolTip(f"{self._name}{count}\n{self._rarity_label} · {cat}"
                        f"{dur}\nBag slot {slot.index}")

    def set_selected(self, on):
        self._selected = on
        self.update()

    def set_edited(self, on):
        self._edited = on
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self)

    def event(self, e):
        if e.type() in (e.Type.HoverEnter, e.Type.HoverLeave):
            self._hover = e.type() == e.Type.HoverEnter
            self.update()
        return super().event(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -2, -2)
        rare = QColor(self._rarity_color)

        # rarity-tinted fill
        fill = QColor(rare)
        fill.setAlphaF(0.16 if (self._hover or self._selected) else 0.10)
        p.setBrush(QBrush(fill))
        if self._selected:
            pen = QPen(QColor(theme.EMBER), 2)
        elif self._edited:
            pen = QPen(QColor(theme.ACCENT), 1.6)
        else:
            edge = QColor(rare)
            edge.setAlphaF(0.85 if self._hover else 0.5)
            pen = QPen(edge, 1)
        p.setPen(pen)
        p.drawRoundedRect(rect, 9, 9)

        # the category glyph, tinted by rarity
        glyph = icons.pixmap(self._icon, self._rarity_color, 18)
        p.drawPixmap(rect.center().x() - 9, rect.top() + 6, glyph)

        # count badge
        if self.slot.count is not None:
            p.setPen(QPen(QColor(theme.TEXT)))
            f = p.font()
            f.setPixelSize(9)
            f.setBold(True)
            p.setFont(f)
            p.drawText(rect.adjusted(0, 0, -4, -3),
                       Qt.AlignRight | Qt.AlignBottom, str(self.slot.count))

        # durability sliver
        if self.slot.durability is not None:
            frac = max(0.06, min(1.0, self.slot.durability / 2000))
            bar = QColor(theme.ACCENT if frac > 0.3 else theme.AMBER)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bar))
            p.drawRoundedRect(rect.left() + 5, rect.bottom() - 4,
                              int((rect.width() - 10) * frac), 2, 1, 1)


class TabChip(QPushButton):
    def __init__(self, text, icon_name, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(32)
        self.setIcon(icons.icon(icon_name, theme.GOLD_TEXT, 15))
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {theme.TEXT_DIM};
                border: 1px solid transparent; border-radius: 9px;
                padding: 0 14px; font-size: 12.5px; font-weight: 650;
            }}
            QPushButton:hover {{ color: {theme.GOLD_TEXT}; }}
            QPushButton:checked {{
                background: rgba(232,162,61,0.12); color: {theme.GOLD_TEXT};
                border-color: rgba(232,162,61,0.45);
            }}""")


class GrimoirePage(QWidget):
    back_requested = Signal()
    bargain_requested = Signal(object, object)          # char_path, EditPlan
    ritual_started = Signal(object)
    ritual_finished = Signal()
    label_saved = Signal(str, str)
    inscribe_requested = Signal(object)                 # char_path
    absorb_requested = Signal(object, object, str, str) # path, knowledge, source, summary
    offer_requested = Signal(object)                    # char_path
    gift_browse_requested = Signal(object)              # char_path
    conjure_requested = Signal(object)                  # char_path
    complete_codex_requested = Signal(object)           # char_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._infos = []
        self._labels = {}
        self._skill_edits = {}
        self._bag_edits = {}        # slot index -> {"count": int|None, "repair": bool}
        self._bag_cells = {}
        self._bag_selected = None
        self._ritual_pending = False

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
        self.ritual_btn = widgets.make_button("Identify ritual", "subtle",
                                              "sparkle", height=30)
        self.ritual_btn.clicked.connect(self._ritual)
        header.addWidget(self.ritual_btn)
        root.addLayout(header)

        flavor = QLabel("“Everything has a price. Yours is a copy of who you were.”")
        flavor.setStyleSheet(
            f"font-family: '{theme.voice_family()}'; font-style: italic;"
            f"color: {theme.TEXT_DIM}; font-size: 13.5px; background: transparent;")
        flavor.setWordWrap(True)
        root.addWidget(flavor)
        root.addSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(8)
        self.char_combo = QComboBox()
        self.char_combo.setFixedHeight(32)
        self.char_combo.setMinimumWidth(150)
        self.char_combo.currentIndexChanged.connect(lambda _: self._render_all())
        top_row.addWidget(self.char_combo)
        top_row.addStretch(1)
        self.tab_skills = TabChip("Skills", "skill-attack")
        self.tab_bag = TabChip("The Bag", "gem")
        self.tab_mirror = TabChip("Mirror", "cat-ring")
        self.tab_scrolls = TabChip("Scrolls", "scroll")
        self._tabs = (self.tab_skills, self.tab_bag, self.tab_mirror,
                      self.tab_scrolls)
        for i, chip in enumerate(self._tabs):
            chip.clicked.connect(lambda _=False, idx=i: self._switch_tab(idx))
            top_row.addWidget(chip)
        root.addLayout(top_row)
        root.addSpacing(10)

        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")
        self._skills_tab = self._make_scroll_tab()
        self._bag_tab = self._make_scroll_tab()
        self._mirror_tab = self._make_scroll_tab()
        self._scrolls_tab = self._make_scroll_tab()
        for tab in (self._skills_tab, self._bag_tab, self._mirror_tab,
                    self._scrolls_tab):
            self.stack.addWidget(tab)
        root.addWidget(self.stack, 1)
        root.addSpacing(10)

        buttons = QHBoxLayout()
        self.warn = QLabel("Experimental · checkpoint taken before every bargain · "
                           "game must be closed")
        self.warn.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 10.5px;"
                                f"background: transparent;")
        self.warn.setWordWrap(True)
        buttons.addWidget(self.warn, 1)
        seal = widgets.PlayButton("SEAL THE BARGAIN", variant="ember",
                                  glow_color=theme.EMBER, height=46,
                                  point_size=10.5)
        seal.setMinimumWidth(210)
        seal.clicked.connect(self._seal)
        buttons.addWidget(seal)
        root.addLayout(buttons)

        self.tab_skills.setChecked(True)

    def _make_scroll_tab(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")
        scroll.viewport().setStyleSheet("background: transparent;")
        return scroll

    @staticmethod
    def _fresh_body(scroll: QScrollArea):
        """Replace the tab's whole body — surgical layout clearing inside a
        QScrollArea proved glitchy (widgets left with stale geometry)."""
        old = scroll.takeWidget()
        if old is not None:
            old.deleteLater()
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        box = QVBoxLayout(body)
        box.setContentsMargins(2, 2, 10, 2)
        box.setSpacing(10)
        scroll.setWidget(body)
        return box

    def _switch_tab(self, index):
        for i, chip in enumerate(self._tabs):
            chip.setChecked(i == index)
        self.stack.setCurrentIndex(index)

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

        gold = QColor(theme.EMBER)
        gold.setAlphaF(0.07)
        p.setPen(QPen(gold, 1.2))
        p.setBrush(Qt.NoBrush)
        r_outer, r_inner = w * 0.52, w * 0.40
        p.drawEllipse(QPointF(cx, cy), r_outer, r_outer)
        p.drawEllipse(QPointF(cx, cy), r_inner, r_inner)
        for i in range(24):
            a = math.radians(self._angle + i * 15)
            p.drawLine(QPointF(cx + math.cos(a) * r_inner, cy + math.sin(a) * r_inner),
                       QPointF(cx + math.cos(a) * (r_inner + 8),
                               cy + math.sin(a) * (r_inner + 8)))
        diamond = QColor(theme.EMBER)
        diamond.setAlphaF(0.12)
        p.setBrush(QBrush(diamond))
        p.setPen(Qt.NoPen)
        for i in range(4):
            a = math.radians(-self._angle * 0.6 + i * 90)
            p.save()
            p.translate(cx + math.cos(a) * r_outer, cy + math.sin(a) * r_outer)
            p.rotate(45)
            p.drawRect(-3, -3, 6, 6)
            p.restore()

        ember = QColor(theme.EMBER_HI)
        for em in self._embers:
            a = 0.10 + 0.10 * math.sin(self._angle * 0.1 + em["phase"])
            ember.setAlphaF(max(0.0, a))
            p.setBrush(QBrush(ember))
            p.drawEllipse(QPointF(em["x"] * w, em["y"] * h), em["size"], em["size"])
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
        self._render_all()

    def _current_info(self):
        i = self.char_combo.currentIndex()
        return self._infos[i] if 0 <= i < len(self._infos) else None

    def _current_data(self):
        info = self._current_info()
        if not info:
            return None
        try:
            return json.loads(info.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def skill_label(self, skill_id, index):
        return skill_label(skill_id, index, self._labels)

    def _render_all(self):
        self._bag_edits = {}
        self._bag_selected = None
        self._mirror_combos = {}
        self._render_skills()
        self._render_bag()
        self._render_mirror()
        self._render_scrolls()

    def _empty_note(self, box, text):
        note = QLabel(text)
        note.setWordWrap(True)
        note.setAlignment(Qt.AlignCenter)
        note.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px;"
                           f"padding: 24px; background: transparent;")
        box.addWidget(note)
        box.addStretch(1)

    # -- skills tab --------------------------------------------------------------
    def _render_skills(self):
        box = self._fresh_body(self._skills_tab)
        self._skill_edits = {}
        info = self._current_info()
        if not info:
            self._empty_note(box, "No characters found on this PC.")
            return

        card = QFrame()
        card.setObjectName("GlassCard")
        grid = QVBoxLayout(card)
        grid.setContentsMargins(12, 6, 12, 6)
        grid.setSpacing(0)
        rows = sorted(enumerate(info.skills),
                      key=lambda t: self.skill_label(t[1]["Id"], t[0]).lower())
        for order, (i, skill) in enumerate(rows):
            grid.addWidget(self._skill_row(skill, i, order, first=(order == 0)))
        box.addWidget(card)

        boons_head = QLabel("QUICK BOONS")
        boons_head.setObjectName("SettingsSection")
        boons_head.setStyleSheet("background: transparent;")
        box.addWidget(boons_head)
        self.heal_check = QCheckBox("Restore vitals — health, stamina, food, water")
        self.repair_check = QCheckBox("Repair everything carried and worn")
        self.cleanse_check = QCheckBox("Cleanse all status effects (poison, burning, cold…)")
        self.hardcore_check = QCheckBox("Lift the hardcore curse (disable hardcore)")
        boons = [self.heal_check, self.repair_check, self.cleanse_check]
        data = self._current_data()
        if data and characters.is_hardcore(data):
            boons.append(self.hardcore_check)
        for c in boons:
            c.setStyleSheet("background: transparent;")
            box.addWidget(c)
        box.addStretch(1)

    def _skill_row(self, skill, index, order, first=False):
        row = QWidget()
        row.setStyleSheet("background: transparent;" if first else
                          "background: transparent;"
                          "border-top: 1px solid rgba(232,162,61,0.10);")
        rl = QHBoxLayout(row)
        rl.setContentsMargins(0, 7, 0, 7)
        rl.setSpacing(10)

        label_text = self.skill_label(skill["Id"], index)
        rl.addWidget(SkillMedallion(icons.skill_icon_name(label_text)))

        col = QVBoxLayout()
        col.setSpacing(3)
        current_xp = int(skill.get("Xp") or 0)
        level = levels.level_for_xp(current_xp)
        top_line = QHBoxLayout()
        top_line.setSpacing(8)
        name = QLabel(label_text)
        name.setStyleSheet("border: none; background: transparent;"
                           "font-size: 13px; font-weight: 650;")
        lv = QLabel(f"Lv {level}")
        lv.setStyleSheet(f"border: none; background: transparent;"
                         f"color: {theme.EMBER_HI}; font-size: 12px; font-weight: 700;")
        xp = QLabel(f"{current_xp:,} xp")
        xp.setStyleSheet(f"border: none; background: transparent;"
                         f"color: {theme.TEXT_FAINT}; font-size: 11px;")
        top_line.addWidget(name)
        top_line.addWidget(lv)
        top_line.addWidget(xp)
        top_line.addStretch(1)
        col.addLayout(top_line)

        floor = levels.req_xp(level)
        ceiling = levels.req_xp(min(level + 1, levels.MAX_LEVEL))
        frac = 1.0 if ceiling <= floor else (current_xp - floor) / (ceiling - floor)
        col.addWidget(XPBar(frac, delay_ms=order * 70))
        rl.addLayout(col, 1)

        combo = QComboBox()
        combo.setFixedSize(88, 30)
        combo.addItem("Keep", None)
        for lvl in range(2, levels.MAX_LEVEL + 1):
            combo.addItem(f"Lv {lvl}", lvl)
        combo.setToolTip("Pick the level this skill should be")
        rl.addWidget(combo)

        edit = QLineEdit()
        edit.setPlaceholderText("xp")
        edit.setValidator(QIntValidator(0, 99_999_999))
        edit.setFixedSize(66, 30)
        edit.setToolTip("Exact xp (overrides the level pick)")
        rl.addWidget(edit)

        self._skill_edits[skill["Id"]] = (combo, edit)
        return row

    # -- bag tab -------------------------------------------------------------------
    def _render_bag(self):
        box = self._fresh_body(self._bag_tab)
        self._bag_cells = {}
        data = self._current_data()
        if not data:
            self._empty_note(box, "No characters found on this PC.")
            return
        slots, _max = characters.list_inventory(data)
        equipped = characters.list_loadout(data)
        if not slots and not equipped:
            self._empty_note(box, "The bag is empty — go pick something up first.")
            return

        card = QFrame()
        card.setObjectName("GlassCard")
        wrap = QVBoxLayout(card)
        wrap.setContentsMargins(14, 10, 14, 12)
        wrap.setSpacing(8)

        # equipped gear (Loadout container — keyed "L<index>")
        if equipped:
            self._add_pouch(wrap, "Equipped", [("L", s) for s in equipped])
        # main inventory, grouped into the game's pouches
        by_pouch = {}
        for slot in slots:
            by_pouch.setdefault(items.pouch(slot.item_data), []).append(slot)
        for pouch_name, _cats in items.POUCHES:
            group = by_pouch.get(pouch_name)
            if group:
                self._add_pouch(wrap, pouch_name, [("", s) for s in group])
        wrap.addSpacing(2)

        self.bag_editor = QWidget()
        self.bag_editor.setStyleSheet("background: transparent;")
        ed = QHBoxLayout(self.bag_editor)
        ed.setContentsMargins(0, 2, 0, 0)
        ed.setSpacing(8)
        self.bag_label = QLabel("Pick a slot above")
        self.bag_label.setStyleSheet(f"border: none; background: transparent;"
                                     f"color: {theme.TEXT_DIM}; font-size: 12px;")
        ed.addWidget(self.bag_label, 1)
        self.bag_count = QLineEdit()
        self.bag_count.setPlaceholderText("count")
        self.bag_count.setValidator(QIntValidator(1, 9999))
        self.bag_count.setFixedSize(70, 28)
        self.bag_count.textEdited.connect(self._bag_count_edited)
        ed.addWidget(self.bag_count)
        for text, value in (("Max", "max"), ("×2", None)):
            chip = QPushButton(text)
            chip.setProperty("variant", "chip")
            chip.setCursor(Qt.PointingHandCursor)
            chip.setFixedHeight(24)
            chip.clicked.connect(lambda _=False, v=value: self._bag_quick(v))
            ed.addWidget(chip)
        self.bag_repair = QPushButton("Repair")
        self.bag_repair.setProperty("variant", "chip")
        self.bag_repair.setCursor(Qt.PointingHandCursor)
        self.bag_repair.setFixedHeight(24)
        self.bag_repair.clicked.connect(self._bag_repair_clicked)
        ed.addWidget(self.bag_repair)
        wrap.addWidget(self.bag_editor)
        box.addWidget(card)

        beyond = QLabel("BEYOND THE BAG")
        beyond.setObjectName("SettingsSection")
        beyond.setStyleSheet("background: transparent;")
        box.addWidget(beyond)
        conjure_row = QHBoxLayout()
        conjure_row.setSpacing(8)
        conjure = widgets.make_button("Conjure an item…", "ember", "sparkle",
                                      height=34)
        conjure.setToolTip("Summon any item in the game into a free bag slot")
        conjure.clicked.connect(lambda: self._emit_with_char(self.conjure_requested))
        conjure_row.addWidget(conjure)
        conjure_row.addStretch(1)
        box.addLayout(conjure_row)

        void_row = QHBoxLayout()
        void_row.setSpacing(8)
        offer = widgets.make_button("Offer my bag to friends", "ghost", "gift",
                                    height=34)
        offer.setToolTip("Writes your bag's catalogue to the shared folder")
        offer.clicked.connect(lambda: self._emit_with_char(self.offer_requested))
        receive = widgets.make_button("Receive a gift…", "ghost", "download-cloud",
                                      height=34)
        receive.setToolTip("Take an item from a friend's offered catalogue "
                           "(experimental)")
        receive.clicked.connect(lambda: self._emit_with_char(self.gift_browse_requested))
        void_row.addWidget(offer)
        void_row.addWidget(receive)
        void_row.addStretch(1)
        box.addLayout(void_row)
        box.addStretch(1)

    def _emit_with_char(self, signal):
        info = self._current_info()
        if info:
            signal.emit(info.path)

    def _add_pouch(self, wrap, title, keyed_slots):
        head = QHBoxLayout()
        head.setSpacing(6)
        lbl = QLabel(title.upper())
        lbl.setStyleSheet(
            f"background: transparent; border: none; color: {theme.EMBER};"
            f"font-family: '{theme.display_family()}'; font-size: 10px;"
            f"font-weight: 600; letter-spacing: 1.5px;")
        head.addWidget(lbl)
        count = QLabel(f"{len(keyed_slots)}")
        count.setStyleSheet(f"background: transparent; border: none;"
                            f"color: {theme.TEXT_FAINT}; font-size: 10px;")
        head.addWidget(count)
        head.addStretch(1)
        wrap.addSpacing(2)
        wrap.addLayout(head)

        grid = QGridLayout()
        grid.setSpacing(6)
        for i, (prefix, slot) in enumerate(keyed_slots):
            key = f"{prefix}{slot.index}"
            cell = SlotCell(key, slot, edited=(key in self._bag_edits))
            cell.clicked.connect(self._select_slot)
            self._bag_cells[key] = cell
            grid.addWidget(cell, i // BAG_COLUMNS, i % BAG_COLUMNS)
        grid.setColumnStretch(BAG_COLUMNS, 1)
        wrap.addLayout(grid)

    def _select_slot(self, cell):
        self._bag_selected = cell
        for key, other in self._bag_cells.items():
            other.set_selected(key == cell.key)
        slot = cell.slot
        rarity_label, rarity_color = items.rarity(slot.item_data)
        name = items.name(slot.item_data)
        parts = [f"<b>{name}</b>",
                 f"<span style='color:{rarity_color}'>{rarity_label}</span>"]
        if slot.count is not None:
            parts.append(f"×{slot.count}")
        if slot.durability is not None:
            parts.append(f"dura {slot.durability}")
        pending = self._bag_edits.get(cell.key) or {}
        tail = []
        if pending.get("count"):
            tail.append(f"→ ×{pending['count']}")
        if pending.get("repair"):
            tail.append("→ repaired")
        text = "  ·  ".join(parts)
        if tail:
            text += f"  <span style='color:{theme.ACCENT}'>{' '.join(tail)}</span>"
        self.bag_label.setText(text)
        self.bag_count.setEnabled(slot.count is not None)
        self.bag_count.setText(str(pending.get("count") or ""))
        max_stack = items.max_stack(slot.item_data)
        self.bag_count.setToolTip(f"Max stack for this item: {max_stack}")
        self.bag_repair.setEnabled(slot.durability is not None)

    def _bag_edit(self, key) -> dict:
        return self._bag_edits.setdefault(key, {"count": None, "repair": False})

    def _bag_count_edited(self, text):
        if not self._bag_selected:
            return
        edit = self._bag_edit(self._bag_selected.key)
        edit["count"] = int(text) if text.strip() else None
        self._bag_selected.set_edited(bool(edit["count"] or edit["repair"]))

    def _bag_quick(self, value):
        if not self._bag_selected or self._bag_selected.slot.count is None:
            return
        cap = items.max_stack(self._bag_selected.slot.item_data)
        if value == "max":
            value = cap
        elif value is None:   # ×2
            base = int(self.bag_count.text()) if self.bag_count.text().strip() \
                else self._bag_selected.slot.count
            value = min(cap, base * 2)
        self.bag_count.setText(str(value))
        self._bag_count_edited(self.bag_count.text())

    def _bag_repair_clicked(self):
        if not self._bag_selected:
            return
        edit = self._bag_edit(self._bag_selected.key)
        edit["repair"] = not edit["repair"]
        self._bag_selected.set_edited(bool(edit["count"] or edit["repair"]))
        self._select_slot(self._bag_selected)

    # -- mirror tab (the barbershop) ---------------------------------------------------
    def _render_mirror(self):
        box = self._fresh_body(self._mirror_tab)
        self._mirror_combos = {}
        self._mirror_original = {}
        data = self._current_data()
        if not data:
            self._empty_note(box, "No characters found on this PC.")
            return
        rows = characters.appearance_rows(data)
        self._mirror_original = dict(rows)

        top = QHBoxLayout()
        top.setSpacing(16)
        self.portrait = widgets.Portrait(128)
        self.portrait.set_appearance(rows)
        top.addWidget(self.portrait, 0, Qt.AlignTop)

        controls = QVBoxLayout()
        controls.setSpacing(9)
        intro = QLabel("The Mirror reflects who you choose to be. Colours and "
                       "styles use the game's own presets.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;"
                            f"background: transparent;")
        controls.addWidget(intro)

        fields = [
            ("SkinTone", "Skin tone", characters.APPEARANCE_RANGES["SkinTone"]),
            ("HairPreset", "Hair style", characters.APPEARANCE_RANGES["HairPreset"] + ["None"]),
            ("HairColor", "Hair colour", characters.APPEARANCE_RANGES["HairColor"]),
            ("FacialHairPreset", "Facial hair",
             characters.facial_hair_options(rows.get("FacialHairPreset"))),
            ("EyeColor", "Eye colour", characters.APPEARANCE_RANGES["EyeColor"]),
            ("EyebrowColor", "Brow colour", characters.APPEARANCE_RANGES["EyebrowColor"]),
        ]
        for slot, label, options in fields:
            if slot not in rows:
                continue
            row = QHBoxLayout()
            row.setSpacing(8)
            lbl = QLabel(label)
            lbl.setStyleSheet(f"background: transparent; color: {theme.TEXT_DIM};"
                              f"font-size: 12px;")
            lbl.setMinimumWidth(84)
            row.addWidget(lbl)
            combo = QComboBox()
            combo.setFixedHeight(30)
            current = rows.get(slot)
            opts = list(options)
            if current and current not in opts:
                opts.insert(0, current)
            for opt in opts:
                combo.addItem(self._pretty_appearance(slot, opt), opt)
            if current:
                combo.setCurrentIndex(max(0, opts.index(current)))
            combo.currentIndexChanged.connect(lambda _=0: self._mirror_preview())
            self._mirror_combos[slot] = combo
            row.addWidget(combo, 1)
            controls.addLayout(row)
        top.addLayout(controls, 1)
        box.addLayout(top)
        box.addStretch(1)

    @staticmethod
    def _pretty_appearance(slot, value):
        if value in ("None", None):
            return "None"
        for prefix in ("SkinTone", "Preset", "Color"):
            if str(value).startswith(prefix) and value[len(prefix):].isdigit():
                return f"{prefix.replace('SkinTone', 'Tone')} {value[len(prefix):]}"
        if "Preset" in str(value):   # facial hair like M_D_Preset4
            tail = value.split("Preset", 1)[1]
            return "None" if tail == "None" else f"Style {tail}"
        return value

    def _mirror_preview(self):
        if not hasattr(self, "portrait"):
            return
        rows = dict(self._mirror_original)
        for slot, combo in self._mirror_combos.items():
            rows[slot] = combo.currentData()
        self.portrait.set_appearance(rows)

    def _mirror_changes(self) -> dict:
        changes = {}
        for slot, combo in getattr(self, "_mirror_combos", {}).items():
            value = combo.currentData()
            if value and value != self._mirror_original.get(slot):
                changes[slot] = value
        return changes

    # -- scrolls tab ------------------------------------------------------------------
    def _render_scrolls(self):
        box = self._fresh_body(self._scrolls_tab)
        data = self._current_data()
        if not data:
            self._empty_note(box, "No characters found on this PC.")
            return
        counts = characters.knowledge_counts(data)

        intro = QLabel("Everything this character has learned. Knowledge can be "
                       "shared — absorbed from another character, or through "
                       "scrolls left in the shared folder.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;"
                            f"background: transparent;")
        box.addWidget(intro)

        icon_map = {"recipes": "book-open", "buildings": "skill-construction",
                    "spells": "skill-magic", "journal": "feather",
                    "shrines": "sparkle", "mounts": "horseshoe",
                    "landmarks": "flag"}
        grid = QGridLayout()
        grid.setSpacing(8)
        cats = list(characters.KNOWLEDGE_DISPLAY) + [("map_regions", "Map regions")]
        shown = 0
        for key, label in cats:
            if key not in counts:
                continue
            card = self._stat_card(icon_map.get(key, "map"), counts[key], label,
                                   delay_ms=shown * 60)
            grid.addWidget(card, shown // 3, shown % 3)
            shown += 1
        box.addLayout(grid)

        fix_head = QLabel("AFTER LEVELLING")
        fix_head.setObjectName("SettingsSection")
        fix_head.setStyleSheet("background: transparent;")
        box.addWidget(fix_head)
        fix_note = QLabel("Raising a skill's level doesn't replay the game's "
                          "unlock events, so you can end up missing spells, "
                          "recipes and buildings your level has earned — and "
                          "spells that never made it onto your spell bar. This "
                          "grants everything unlockable and fills the bar.")
        fix_note.setWordWrap(True)
        fix_note.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11.5px;"
                               f"background: transparent;")
        box.addWidget(fix_note)
        codex_row = QHBoxLayout()
        codex = widgets.make_button("Complete the codex", "ember", "book-open",
                                    height=36)
        codex.setToolTip("Learn every recipe, spell and building, and put "
                         "unlocked spells on your spell bar")
        codex.clicked.connect(
            lambda: self._emit_with_char(self.complete_codex_requested))
        codex_row.addWidget(codex)
        codex_row.addStretch(1)
        box.addLayout(codex_row)

        actions_head = QLabel("SHARE KNOWLEDGE")
        actions_head.setObjectName("SettingsSection")
        actions_head.setStyleSheet("background: transparent;")
        box.addWidget(actions_head)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        absorb_char = widgets.make_button("Absorb from a character…", "ghost",
                                          "dragon", height=34)
        absorb_char.clicked.connect(self._absorb_from_character)
        row1.addWidget(absorb_char)
        row1.addStretch(1)
        box.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        inscribe = widgets.make_button("Inscribe my scroll", "ghost", "feather",
                                       height=34)
        inscribe.setToolTip("Leaves this character's knowledge in the shared "
                            "folder for friends")
        inscribe.clicked.connect(lambda: self._emit_with_char(self.inscribe_requested))
        absorb_scroll = widgets.make_button("Absorb a scroll…", "ghost", "scroll",
                                            height=34)
        absorb_scroll.clicked.connect(self._absorb_from_scroll)
        row2.addWidget(inscribe)
        row2.addWidget(absorb_scroll)
        row2.addStretch(1)
        box.addLayout(row2)
        box.addStretch(1)

    def _stat_card(self, icon_name, count, label, delay_ms=0):
        card = QFrame()
        card.setObjectName("GlassCard")
        lay = QHBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(9)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.EMBER_HI, 18))
        ic.setStyleSheet("background: transparent; border: none;")
        lay.addWidget(ic)
        col = QVBoxLayout()
        col.setSpacing(0)
        num = QLabel(f"{count:,}")
        num.setStyleSheet(f"background: transparent; border: none; font-size: 16px;"
                          f"font-weight: 700; color: {theme.GOLD_TEXT};"
                          f"font-family: '{theme.display_family()}';")
        cap = QLabel(label)
        cap.setStyleSheet(f"background: transparent; border: none;"
                          f"color: {theme.TEXT_FAINT}; font-size: 10.5px;")
        col.addWidget(num)
        col.addWidget(cap)
        lay.addLayout(col, 1)
        return card

    def _summary(self, gains: dict) -> str:
        names = dict(characters.KNOWLEDGE_DISPLAY)
        names["map_regions"] = "map regions"
        bits = [f"+{n} {names.get(k, k).lower()}" for k, n in gains.items()]
        return ", ".join(bits)

    def _absorb_from_character(self):
        info = self._current_info()
        data = self._current_data()
        others = [i for i in self._infos if i.path != info.path] if info else []
        if not info or not others:
            return
        from PySide6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getItem(
            self, "Absorb knowledge", "Learn everything known by:",
            [o.name for o in others], 0, False)
        if not ok:
            return
        source = next(o for o in others if o.name == name)
        try:
            source_data = json.loads(source.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        knowledge = characters.extract_knowledge(source_data)
        gains = characters.diff_knowledge(data, knowledge)
        self.absorb_requested.emit(info.path, knowledge, name,
                                   self._summary(gains) if gains else "")

    def _absorb_from_scroll(self):
        info = self._current_info()
        data = self._current_data()
        if not info:
            return
        # the window supplies scrolls via set_scrolls before opening
        scrolls = self._available_scrolls or []
        if not scrolls:
            return
        from PySide6.QtWidgets import QInputDialog
        labels = [f"{s.get('author', '?')} — {s.get('character', '?')}" for s in scrolls]
        choice, ok = QInputDialog.getItem(
            self, "Absorb a scroll", "Scrolls left in the shared folder:",
            labels, 0, False)
        if not ok:
            return
        payload = scrolls[labels.index(choice)]
        knowledge = payload.get("knowledge") or {}
        gains = characters.diff_knowledge(data, knowledge)
        self.absorb_requested.emit(info.path, knowledge, payload.get("author", "?"),
                                   self._summary(gains) if gains else "")

    _available_scrolls = []

    def set_scrolls(self, scrolls):
        self._available_scrolls = scrolls or []

    # -- seal ------------------------------------------------------------------------
    def _seal(self):
        info = self._current_info()
        if not info:
            return
        plan = EditPlan(heal_vitals=self.heal_check.isChecked(),
                        repair_all=self.repair_check.isChecked(),
                        cleanse=self.cleanse_check.isChecked(),
                        disable_hardcore=self.hardcore_check.isChecked())
        for skill_id, (combo, edit) in self._skill_edits.items():
            text = edit.text().strip()
            if text:
                plan.skill_xp[skill_id] = int(text)
                continue
            level = combo.currentData()
            if level:
                plan.skill_xp[skill_id] = levels.xp_for_level(level)
        for key, edit in self._bag_edits.items():
            if edit.get("count"):
                plan.item_counts[key] = edit["count"]
            if edit.get("repair"):
                plan.item_repairs.add(key)
        plan.appearance.update(self._mirror_changes())
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
