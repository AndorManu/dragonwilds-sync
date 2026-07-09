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

from PySide6.QtCore import (Property, QEasingCurve, QPoint, QPointF,
                            QPropertyAnimation, Qt, QTimer, Signal)
from PySide6.QtGui import QBrush, QColor, QIntValidator, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import (QApplication, QCheckBox, QComboBox, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QMenu,
                               QPushButton, QScrollArea, QStackedWidget,
                               QVBoxLayout, QWidget)

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
    pip, name tooltip, hover glow. Left-click opens its detail popover;
    right-click opens the quick menu. Its shown state reflects pending edits, so
    changing a count or upgrading a tier updates the cell instantly."""

    clicked = Signal(object)         # the SlotCell itself
    menu_requested = Signal(object)  # right-click -> quick actions menu

    def __init__(self, key, slot, parent=None):
        super().__init__(parent)
        self.key = key
        self.slot = slot              # the original, untouched inventory slot
        self._hover = False
        self._selected = False
        self.setFixedSize(46, 46)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.set_display(slot.item_data, slot.count, slot.durability, edited=False)

    def set_display(self, item_data, count, durability, edited):
        """Show an item + count/durability (may be the staged, not saved, state)."""
        self._item_data = item_data
        self._count = count
        self._durability = durability
        self._edited = edited
        self._name = items.name(item_data)
        self._rarity_label, self._rarity_color = items.rarity(item_data)
        self._icon = items.icon_key(item_data)
        cat = items.category(item_data)
        c = f"  ×{count}" if count is not None else ""
        d = f"\nDurability {durability}" if durability is not None else ""
        mark = "  · pending" if edited else ""
        self.setToolTip(f"{self._name}{c}{mark}\n{self._rarity_label} · {cat}{d}"
                        f"\nClick for details · right-click for quick actions")
        self.update()

    def set_selected(self, on):
        self._selected = on
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self)

    def contextMenuEvent(self, e):
        self.menu_requested.emit(self)

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
        if self._count is not None:
            p.setPen(QPen(QColor(theme.TEXT)))
            f = p.font()
            f.setPixelSize(9)
            f.setBold(True)
            p.setFont(f)
            p.drawText(rect.adjusted(0, 0, -4, -3),
                       Qt.AlignRight | Qt.AlignBottom, str(self._count))

        # durability sliver (repaired items read full; low durability turns amber)
        if self._durability is not None:
            frac = max(0.06, min(1.0, self._durability / 1000))
            bar = QColor(theme.ACCENT if frac > 0.3 else theme.AMBER)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(bar))
            p.drawRoundedRect(rect.left() + 5, rect.bottom() - 4,
                              int((rect.width() - 10) * frac), 2, 1, 1)

        # a pending-edit dot in the top-left corner
        if self._edited:
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(QColor(theme.ACCENT)))
            p.drawEllipse(rect.left() + 4, rect.top() + 4, 4, 4)


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


class ItemPopover(QFrame):
    """A floating detail card anchored beside a bag slot — name, rarity, live
    stats and every per-item action (count, repair, tier up/down). Replaces the
    old detail strip that sat awkwardly at the bottom of the bag. The body is
    rebuilt wholesale on each change (small, and dodges stale-widget glitches)."""

    def __init__(self, page):
        super().__init__(page, Qt.Popup)
        self.page = page
        self.key = None
        self.setObjectName("GlassCard")
        self.setStyleSheet(
            f"QFrame#GlassCard {{ background: {theme.SURFACE};"
            f" border: 1px solid {theme.BORDER}; border-radius: 12px; }}")
        self.setFixedWidth(236)
        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._body = None

    def open_for(self, cell):
        self.key = cell.key
        self._rebuild()
        self.adjustSize()
        self._position(cell)
        self.show()

    def refresh(self):
        if self.isVisible() and self.key is not None:
            self._rebuild()
            self.adjustSize()

    # -- internals ------------------------------------------------------------
    def _rebuild(self):
        if self._body is not None:
            self._outer.removeWidget(self._body)
            self._body.deleteLater()
        self._body = QWidget()
        self._body.setStyleSheet("background: transparent;")
        box = QVBoxLayout(self._body)
        box.setContentsMargins(14, 12, 14, 12)
        box.setSpacing(7)
        self._populate(box)
        self._outer.addWidget(self._body)

    def _chip(self, text, tip=""):
        b = QPushButton(text)
        b.setProperty("variant", "chip")
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(26)
        if tip:
            b.setToolTip(tip)
        return b

    def _section(self, text):
        lbl = QLabel(text.upper())
        lbl.setStyleSheet(
            f"background: transparent; border: none; color: {theme.EMBER};"
            f"font-family: '{theme.display_family()}'; font-size: 9.5px;"
            f"font-weight: 600; letter-spacing: 1.4px;")
        return lbl

    def _populate(self, box):
        page = self.page
        cell = page._bag_cells.get(self.key)
        if not cell:
            return
        slot = cell.slot
        edit = page._bag_edits.get(self.key)
        item_data, count, durability = page._effective(slot, edit)
        r_label, r_color = items.rarity(item_data)
        cat = items.category(item_data)

        title = QLabel(items.name(item_data))
        title.setWordWrap(True)
        title.setStyleSheet(
            f"font-family: '{theme.display_family()}'; font-size: 15px;"
            f"font-weight: 700; color: {r_color}; background: transparent;")
        box.addWidget(title)

        pos, length = items.tier_position(item_data)
        tier_txt = f"  ·  tier {pos}/{length}" if length else ""
        sub = QLabel(f"{r_label} · {cat}{tier_txt}")
        sub.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 11px;"
                          f"background: transparent;")
        box.addWidget(sub)

        if count is not None:
            cap = items.max_stack(item_data)
            stat = QLabel(f"×{count}  /  {cap} max")
        elif durability is not None:
            full = "  · full" if durability >= 1000 else ""
            stat = QLabel(f"Durability {durability}{full}")
        else:
            stat = QLabel("")
        stat.setStyleSheet(f"color: {theme.TEXT}; font-size: 12px; font-weight: 600;"
                           f"background: transparent;")
        box.addWidget(stat)

        # count controls (stackable items)
        if count is not None:
            field = QLineEdit(str(count))
            field.setValidator(QIntValidator(1, 999999))
            field.setFixedHeight(26)
            field.setFixedWidth(66)
            field.editingFinished.connect(
                lambda: page._stage_count(self.key, field.text()))
            row1 = QHBoxLayout()
            row1.setSpacing(5)
            row1.addWidget(field)
            row1.addWidget(self._act("−", lambda: page._nudge_count(self.key, -1)))
            row1.addWidget(self._act("+", lambda: page._nudge_count(self.key, +1)))
            row1.addStretch(1)
            box.addLayout(row1)
            row2 = QHBoxLayout()
            row2.setSpacing(5)
            row2.addWidget(self._act("Max", lambda: page._stage_count(
                self.key, items.max_stack(item_data))))
            row2.addWidget(self._act("×2", lambda: page._nudge_count(self.key, "x2")))
            row2.addWidget(self._act("+100", lambda: page._nudge_count(self.key, +100)))
            row2.addStretch(1)
            box.addLayout(row2)

        # repair (anything with durability)
        if durability is not None:
            staged = bool(edit and edit.get("repair"))
            rb = self._act("Repaired ✓" if staged else "Repair to full",
                           lambda: page._stage_repair(self.key))
            box.addWidget(rb, alignment=Qt.AlignLeft)

        # tier ladder
        down = items.tier_neighbor(item_data, -1)
        up = items.tier_neighbor(item_data, +1)
        if down or up:
            box.addWidget(self._section("Change tier"))
            trow = QHBoxLayout()
            trow.setSpacing(6)
            if down:
                trow.addWidget(self._act(
                    f"▼ {down['material']}",
                    lambda nid=down["id"]: page._stage_swap(self.key, nid),
                    tip=f"Downgrade to {down['name']}"))
            if up:
                trow.addWidget(self._act(
                    f"▲ {up['material']}",
                    lambda nid=up["id"]: page._stage_swap(self.key, nid),
                    tip=f"Upgrade to {up['name']}"))
            trow.addStretch(1)
            box.addLayout(trow)

        if edit and page._is_edited(edit):
            undo = self._act("Undo pending change",
                             lambda: page._clear_edit(self.key))
            box.addWidget(undo, alignment=Qt.AlignLeft)

    def _act(self, text, fn, tip=""):
        b = self._chip(text, tip)
        b.clicked.connect(lambda _=False: fn())
        return b

    def _position(self, cell):
        anchor = cell.mapToGlobal(QPoint(cell.width() + 10, -6))
        x, y = anchor.x(), anchor.y()
        screen = QApplication.primaryScreen().availableGeometry()
        if x + self.width() > screen.right() - 6:
            x = cell.mapToGlobal(QPoint(-self.width() - 10, -6)).x()
        x = max(screen.left() + 6, x)
        if y + self.height() > screen.bottom() - 6:
            y = screen.bottom() - self.height() - 6
        y = max(screen.top() + 6, y)
        self.move(x, y)


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
    learn_requested = Signal(object)                    # char_path

    def __init__(self, parent=None):
        super().__init__(parent)
        self._infos = []
        self._labels = {}
        self._skill_edits = {}
        self._bag_edits = {}        # slot key -> {"count": int|None, "repair": bool, "swap": id|None}
        self._bag_cells = {}
        self._bag_pouches = []      # (header_widget, grid_widget, [cells]) for search
        self._bag_selected = None
        self._popover = None
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
        self._bag_pouches = []
        self._close_popover()
        data = self._current_data()
        if not data:
            self._empty_note(box, "No characters found on this PC.")
            return
        slots, _max = characters.list_inventory(data)
        equipped = characters.list_loadout(data)
        if not slots and not equipped:
            self._empty_note(box, "The bag is empty — go pick something up first.")
            return

        self.bag_search = QLineEdit()
        self.bag_search.setPlaceholderText("Search the bag…")
        self.bag_search.setClearButtonEnabled(True)
        self.bag_search.setFixedHeight(30)
        self.bag_search.textChanged.connect(self._bag_filter)
        box.addWidget(self.bag_search)

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
        box.addWidget(card)

        hint = QLabel("Click an item for its details · right-click for quick actions")
        hint.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;"
                           f"background: transparent;")
        box.addWidget(hint)

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

    def _pouch_btn(self, text, tip=""):
        b = QPushButton(text)
        b.setProperty("variant", "chip")
        b.setCursor(Qt.PointingHandCursor)
        b.setFixedHeight(22)
        if tip:
            b.setToolTip(tip)
        return b

    def _add_pouch(self, wrap, title, keyed_slots):
        slots = [slot for _p, slot in keyed_slots]
        keys = [f"{prefix}{slot.index}" for prefix, slot in keyed_slots]

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

        # pouch-wide bulk actions, only when they'd do something
        if any(items.is_stackable(s.item_data) for s in slots):
            b = self._pouch_btn("Max all", "Fill every stack in this pouch")
            b.clicked.connect(lambda _=False, k=list(keys): self._bulk_max(k))
            head.addWidget(b)
        if any(s.durability is not None for s in slots):
            b = self._pouch_btn("Repair all", "Repair everything in this pouch")
            b.clicked.connect(lambda _=False, k=list(keys): self._bulk_repair(k))
            head.addWidget(b)
        if any(items.tier_neighbor(s.item_data, +1) for s in slots):
            b = self._pouch_btn("Upgrade all", "Raise every item here one tier")
            b.clicked.connect(lambda _=False, k=list(keys): self._bulk_upgrade(k))
            head.addWidget(b)

        header_widget = QWidget()
        header_widget.setStyleSheet("background: transparent;")
        header_widget.setLayout(head)
        wrap.addSpacing(2)
        wrap.addWidget(header_widget)

        grid = QGridLayout()
        grid.setSpacing(6)
        cells = []
        for i, (prefix, slot) in enumerate(keyed_slots):
            key = f"{prefix}{slot.index}"
            cell = SlotCell(key, slot)
            cell.clicked.connect(self._open_popover)
            cell.menu_requested.connect(self._open_menu)
            self._bag_cells[key] = cell
            cells.append(cell)
            grid.addWidget(cell, i // BAG_COLUMNS, i % BAG_COLUMNS)
            if key in self._bag_edits:
                self._refresh_cell(key)
        grid.setColumnStretch(BAG_COLUMNS, 1)
        grid_widget = QWidget()
        grid_widget.setStyleSheet("background: transparent;")
        grid_widget.setLayout(grid)
        wrap.addWidget(grid_widget)
        self._bag_pouches.append((header_widget, grid_widget, cells))

    def _bag_filter(self, text):
        q = (text or "").strip().lower()
        for header, grid_widget, cells in self._bag_pouches:
            any_visible = False
            for cell in cells:
                shown = (not q) or q in items.name(cell.slot.item_data).lower() \
                    or q in items.name(cell._item_data).lower()
                cell.setVisible(shown)
                any_visible = any_visible or shown
            header.setVisible(any_visible)
            grid_widget.setVisible(any_visible)

    # -- staging (edits are held until "Seal the bargain") -----------------------
    def _bag_edit(self, key) -> dict:
        return self._bag_edits.setdefault(
            key, {"count": None, "repair": False, "swap": None})

    def _effective(self, slot, edit):
        """(item_data, count, durability) after applying a pending edit."""
        edit = edit or {}
        item_data = edit.get("swap") or slot.item_data
        if items.is_stackable(item_data):
            base = edit.get("count") or slot.count or 1
            return item_data, max(1, min(int(base), items.max_stack(item_data))), None
        dur = characters.REPAIR_VALUE if (edit.get("repair") or edit.get("swap")) \
            else slot.durability
        return item_data, None, dur

    @staticmethod
    def _is_edited(edit):
        return bool(edit and (edit.get("count") or edit.get("repair") or edit.get("swap")))

    def _refresh_cell(self, key):
        cell = self._bag_cells.get(key)
        if not cell:
            return
        edit = self._bag_edits.get(key)
        item_data, count, dur = self._effective(cell.slot, edit)
        cell.set_display(item_data, count, dur, self._is_edited(edit))
        if not self._is_edited(edit):
            self._bag_edits.pop(key, None)

    def _after_stage(self, key):
        self._refresh_cell(key)
        if (self._popover is not None and self._popover.isVisible()
                and self._popover.key == key):
            self._popover.refresh()

    def _stage_count(self, key, value):
        cell = self._bag_cells.get(key)
        if not cell:
            return
        edit = self._bag_edit(key)
        item_data = edit.get("swap") or cell.slot.item_data
        try:
            value = int(value)
        except (TypeError, ValueError):
            return
        value = max(1, min(value, items.max_stack(item_data)))
        edit["count"] = None if (value == cell.slot.count and not edit.get("swap")) \
            else value
        self._after_stage(key)

    def _nudge_count(self, key, delta):
        cell = self._bag_cells.get(key)
        if not cell:
            return
        _id, cur, _d = self._effective(cell.slot, self._bag_edits.get(key))
        cur = cur or 1
        self._stage_count(key, cur * 2 if delta == "x2" else cur + delta)

    def _stage_repair(self, key, on=None):
        edit = self._bag_edit(key)
        edit["repair"] = (not edit.get("repair")) if on is None else bool(on)
        self._after_stage(key)

    def _stage_swap(self, key, new_id):
        cell = self._bag_cells.get(key)
        if not cell:
            return
        edit = self._bag_edit(key)
        edit["swap"] = None if new_id == cell.slot.item_data else new_id
        # a swap can flip stackable <-> gear; drop the now-meaningless field
        eff_id = edit.get("swap") or cell.slot.item_data
        if items.is_stackable(eff_id):
            edit["repair"] = False
        else:
            edit["count"] = None
        self._after_stage(key)

    def _clear_edit(self, key):
        self._bag_edits.pop(key, None)
        self._after_stage(key)

    def _bulk_max(self, keys):
        for key in keys:
            cell = self._bag_cells.get(key)
            if not cell:
                continue
            eff_id = (self._bag_edits.get(key) or {}).get("swap") or cell.slot.item_data
            if items.is_stackable(eff_id):
                self._stage_count(key, items.max_stack(eff_id))

    def _bulk_repair(self, keys):
        for key in keys:
            cell = self._bag_cells.get(key)
            if cell and cell.slot.durability is not None:
                self._stage_repair(key, True)

    def _bulk_upgrade(self, keys):
        for key in keys:
            cell = self._bag_cells.get(key)
            if not cell:
                continue
            eff_id = (self._bag_edits.get(key) or {}).get("swap") or cell.slot.item_data
            up = items.tier_neighbor(eff_id, +1)
            if up:
                self._stage_swap(key, up["id"])

    # -- popover + right-click menu ----------------------------------------------
    def _ensure_popover(self):
        if self._popover is None:
            self._popover = ItemPopover(self)
        return self._popover

    def _open_popover(self, cell):
        self._bag_selected = cell
        for k, c in self._bag_cells.items():
            c.set_selected(k == cell.key)
        self._ensure_popover().open_for(cell)

    def _close_popover(self):
        if self._popover is not None:
            self._popover.hide()

    def _open_menu(self, cell):
        key = cell.key
        edit = self._bag_edits.get(key)
        item_data, count, dur = self._effective(cell.slot, edit)
        menu = QMenu(self)
        if count is not None:
            cap = items.max_stack(item_data)
            menu.addAction(f"Set to max ({cap})", lambda: self._stage_count(key, cap))
            menu.addAction("+100", lambda: self._nudge_count(key, +100))
            menu.addAction("+1000", lambda: self._nudge_count(key, +1000))
            menu.addAction("×2", lambda: self._nudge_count(key, "x2"))
        if dur is not None:
            menu.addAction("Repair to full", lambda: self._stage_repair(key, True))
        up = items.tier_neighbor(item_data, +1)
        down = items.tier_neighbor(item_data, -1)
        if up or down:
            menu.addSeparator()
            if up:
                menu.addAction(f"▲ Upgrade to {up['name']}",
                               lambda nid=up["id"]: self._stage_swap(key, nid))
            if down:
                menu.addAction(f"▼ Downgrade to {down['name']}",
                               lambda nid=down["id"]: self._stage_swap(key, nid))
        if self._is_edited(edit):
            menu.addSeparator()
            menu.addAction("Undo pending change", lambda: self._clear_edit(key))
        menu.addSeparator()
        menu.addAction("Open details…", lambda: self._open_popover(cell))
        menu.exec(cell.mapToGlobal(QPoint(cell.width() // 2, cell.height() // 2)))

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

        pick_row = QHBoxLayout()
        learn = widgets.make_button("Learn a spell, recipe or building…", "ember",
                                    "book-open", height=34)
        learn.setToolTip("Browse and pick exactly what to unlock")
        learn.clicked.connect(lambda: self._emit_with_char(self.learn_requested))
        pick_row.addWidget(learn)
        pick_row.addStretch(1)
        box.addLayout(pick_row)

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
            if edit.get("swap"):
                plan.item_swaps[key] = edit["swap"]
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
