"""Small reusable pieces: spinner, pulsing dot, avatar, buttons, form fields."""

from pathlib import Path

from PySide6.QtCore import (Property, QEasingCurve, QPropertyAnimation, QSize,
                            Qt, QTimer)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import (QFileDialog, QGraphicsDropShadowEffect, QHBoxLayout,
                               QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget)

from . import format as fmt
from . import icons, theme


class Spinner(QWidget):
    """A rotating arc, the app's only loading indicator."""

    def __init__(self, size=24, line_width=2.6, color=theme.ACCENT, parent=None):
        super().__init__(parent)
        self._size = size
        self._line_width = line_width
        self._color = QColor(color)
        self._angle = 0
        self.setFixedSize(size, size)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._tick)

    def _tick(self):
        self._angle = (self._angle + 5) % 360
        self.update()

    def showEvent(self, e):
        self._timer.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._timer.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(self._color, self._line_width, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        m = self._line_width / 2 + 1
        rect = self.rect().adjusted(m, m, -m, -m)
        p.drawArc(rect, -self._angle * 16, 270 * 16)


class PulsingDot(QWidget):
    """A softly breathing dot — shown while the game is running."""

    def __init__(self, size=14, color=theme.ACCENT, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._level = 1.0
        self.setFixedSize(size, size)
        self._anim = QPropertyAnimation(self, b"level", self)
        self._anim.setStartValue(0.35)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(1100)
        self._anim.setEasingCurve(QEasingCurve.InOutSine)

    def _get_level(self):
        return self._level

    def _set_level(self, v):
        self._level = v
        self.update()

    level = Property(float, _get_level, _set_level)

    def showEvent(self, e):
        self._anim.setLoopCount(-1)
        # ping-pong: restart reversed each cycle via finished is messy; use keyframes
        self._anim.setKeyValueAt(0.0, 0.35)
        self._anim.setKeyValueAt(0.5, 1.0)
        self._anim.setKeyValueAt(1.0, 0.35)
        self._anim.start()
        super().showEvent(e)

    def hideEvent(self, e):
        self._anim.stop()
        super().hideEvent(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        c = QColor(self._color)
        # halo
        c.setAlphaF(0.25 * self._level)
        p.setBrush(QBrush(c))
        p.setPen(Qt.NoPen)
        p.drawEllipse(self.rect())
        # core
        c.setAlphaF(0.55 + 0.45 * self._level)
        p.setBrush(QBrush(c))
        r = self.rect().adjusted(4, 4, -4, -4)
        p.drawEllipse(r)


# Guessed-but-consistent palettes for portrait rendering. They won't match
# the game's exact swatches, but every app renders a given character the
# same way — which is what matters for recognisability.
_SKIN_RAMP = ["#F5DCC0", "#EFD0AC", "#E6BE96", "#D9A87E", "#C79066",
              "#AE7852", "#93613F", "#7A4E31", "#5F3B24", "#4A2C19"]
_HAIR_RAMP = ["#181310", "#2E2117", "#4A331F", "#6B4A2A", "#8F6A3C",
              "#B08D57", "#8C2F1E", "#77787C", "#D8D3C7", "#C9A227"]
_EYE_RAMP = ["#3A2E1E", "#274A66", "#2F5D3A", "#5A5F66", "#6E4A2E", "#8A8F96"]


def _ramp_pick(ramp, row_name, default_index=2):
    digits = "".join(ch for ch in (row_name or "") if ch.isdigit())
    index = int(digits) - 1 if digits else default_index
    return QColor(ramp[max(0, min(index, len(ramp) - 1))])


class Avatar(QWidget):
    """Feed avatar: a character portrait if we know one, else emoji/initials."""

    def __init__(self, name: str, size=30, emoji="", color=None, portrait="",
                 parent=None):
        super().__init__(parent)
        self._name = name or "?"
        self._emoji = emoji or ""
        self._color = color or None
        self._portrait = (portrait or "").split("|") if portrait else None
        if self._portrait and len(self._portrait) < 6:
            self._portrait = None
        self.setFixedSize(size, size)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = QColor(self._color or fmt.name_color(self._name))
        if not base.isValid():
            base = QColor(fmt.name_color(self._name))
        fill = QColor(base)
        fill.setAlphaF(0.18)
        p.setBrush(QBrush(fill))
        p.setPen(QPen(base, 1.2))
        p.drawEllipse(self.rect().adjusted(1, 1, -1, -1))

        if self._portrait:
            self._paint_portrait(p)
            return
        f = QFont(self.font())
        if self._emoji:
            f.setPixelSize(int(self.height() * 0.5))
            p.setFont(f)
            p.setPen(QPen(QColor(theme.TEXT)))
            p.drawText(self.rect(), Qt.AlignCenter, self._emoji)
        else:
            f.setPixelSize(int(self.height() * 0.38))
            f.setWeight(QFont.DemiBold)
            p.setFont(f)
            p.setPen(QPen(base))
            p.drawText(self.rect(), Qt.AlignCenter, fmt.initials(self._name))

    def _paint_portrait(self, p: QPainter):
        paint_bust(p, self.rect(), self._portrait, shoulders=True)


def paint_bust(p: QPainter, rect, descriptor_parts, shoulders=True):
    """Stylised bust from an appearance descriptor: skin, hair, beard, eyes.
    Shared by the feed Avatar and the Mirror's live preview."""
    _body, skin_row, hair_preset, hair_row, facial_row, eye_row = descriptor_parts[:6]
    x0, y0, s = rect.left(), rect.top(), rect.height()
    skin = _ramp_pick(_SKIN_RAMP, skin_row)
    hair = _ramp_pick(_HAIR_RAMP, hair_row)
    eyes = _ramp_pick(_EYE_RAMP, eye_row, 1)

    p.setClipRect(rect.adjusted(2, 2, -2, -2))
    p.setPen(Qt.NoPen)

    if shoulders:
        p.setBrush(QBrush(QColor(theme.SURFACE_2)))
        p.drawEllipse(x0 + int(s * 0.12), y0 + int(s * 0.72),
                      int(s * 0.76), int(s * 0.55))
    p.setBrush(QBrush(skin))
    head_x, head_y = x0 + int(s * 0.28), y0 + int(s * 0.22)
    head_w, head_h = int(s * 0.44), int(s * 0.50)
    p.drawEllipse(head_x, head_y, head_w, head_h)

    preset = (hair_preset or "").lower()
    if "none" not in preset and "bald" not in preset:
        digits = "".join(ch for ch in preset if ch.isdigit())
        style = (int(digits) if digits else 0) % 3
        p.setBrush(QBrush(hair))
        if style == 0:
            p.drawChord(head_x - 1, head_y - int(s * 0.04),
                        head_w + 2, int(head_h * 0.72), 0, 180 * 16)
        elif style == 1:
            p.drawChord(head_x - int(s * 0.05), head_y - int(s * 0.05),
                        head_w + int(s * 0.10), int(head_h * 0.95), 0, 180 * 16)
        else:
            p.drawChord(head_x, head_y - int(s * 0.07),
                        head_w, int(head_h * 0.62), 0, 180 * 16)
            p.drawEllipse(x0 + int(s * 0.44), y0 + int(s * 0.10),
                          int(s * 0.14), int(s * 0.12))

    if "none" not in (facial_row or "").lower():
        beard = QColor(hair).darker(115)
        p.setBrush(QBrush(beard))
        p.drawChord(head_x + int(head_w * 0.14), head_y + int(head_h * 0.52),
                    int(head_w * 0.72), int(head_h * 0.52), 180 * 16, 180 * 16)

    p.setBrush(QBrush(eyes))
    eye_y = head_y + int(head_h * 0.42)
    r = max(1, int(s * 0.045))
    p.drawEllipse(head_x + int(head_w * 0.26) - r, eye_y - r, r * 2, r * 2)
    p.drawEllipse(head_x + int(head_w * 0.72) - r, eye_y - r, r * 2, r * 2)


class Portrait(QWidget):
    """A larger live portrait for the Mirror; set from an appearance dict."""

    def __init__(self, size=132, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._parts = ["", "SkinTone4", "Preset1", "Color4", "None", "Color2"]

    def set_appearance(self, rows: dict):
        self._parts = [
            rows.get("BodyType", ""), rows.get("SkinTone", "SkinTone4"),
            rows.get("HairPreset", "Preset1"), rows.get("HairColor", "Color4"),
            rows.get("FacialHairPreset", "None"), rows.get("EyeColor", "Color2")]
        self.update()

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        base = QColor(theme.EMBER)
        ring = QColor(base)
        ring.setAlphaF(0.10)
        p.setBrush(QBrush(ring))
        p.setPen(QPen(QColor(base.red(), base.green(), base.blue(), 90), 1.4))
        p.drawEllipse(self.rect().adjusted(1, 1, -2, -2))
        paint_bust(p, self.rect(), self._parts, shoulders=True)


class OptionCard(QWidget):
    """A large clickable choice card (onboarding fork)."""

    def __init__(self, icon_name, title, description, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = False
        self.setAttribute(Qt.WA_Hover, True)

        row = QHBoxLayout(self)
        row.setContentsMargins(18, 16, 16, 16)
        row.setSpacing(14)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, theme.ACCENT, 22))
        ic.setStyleSheet("background: transparent;")
        row.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(3)
        t = QLabel(title)
        t.setStyleSheet("background: transparent; font-size: 14px; font-weight: 650;")
        d = QLabel(description)
        d.setWordWrap(True)
        d.setStyleSheet(f"background: transparent; color: {theme.TEXT_DIM}; font-size: 12px;")
        col.addWidget(t)
        col.addWidget(d)
        row.addLayout(col, 1)

    # clicked is wired via mousePressEvent -> callback for simplicity
    def set_on_click(self, callback):
        self._on_click = callback

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton and getattr(self, "_on_click", None):
            self._on_click()

    def event(self, e):
        if e.type() in (e.Type.HoverEnter, e.Type.HoverLeave):
            self._hover = e.type() == e.Type.HoverEnter
            self.update()
        return super().event(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        bg = QColor(theme.SURFACE_2 if self._hover else theme.SURFACE)
        border = QColor(theme.ACCENT if self._hover else theme.BORDER)
        p.setBrush(QBrush(bg))
        p.setPen(QPen(border, 1))
        p.drawRoundedRect(self.rect().adjusted(0, 0, -1, -1), 12, 12)


def make_button(text="", variant="ghost", icon_name=None, icon_color=None,
                height=40, parent=None) -> QPushButton:
    btn = QPushButton(text, parent)
    btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setFixedHeight(height)
    if icon_name:
        btn.setIcon(icons.icon(icon_name, icon_color or theme.TEXT_DIM))
        btn.setIconSize(QSize(17, 17))
    return btn


def icon_button(icon_name, color=theme.TEXT_DIM, variant="icon", size=16,
                tooltip="", parent=None) -> QPushButton:
    btn = QPushButton(parent)
    btn.setProperty("variant", variant)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setIcon(icons.icon(icon_name, color, size))
    btn.setIconSize(QSize(size, size))
    if tooltip:
        btn.setToolTip(tooltip)
    return btn


class PlayButton(QPushButton):
    """The showpiece action: gradient fill with a glow that breathes at
    rest and flares on hover. Emerald by default; ember for the grimoire."""

    def __init__(self, text="PLAY", parent=None, variant="primary",
                 glow_color=None, height=60, point_size=12.5):
        super().__init__(text, parent)
        self.setProperty("variant", variant)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(height)
        f = QFont(self.font())
        f.setPointSizeF(point_size)
        f.setWeight(QFont.Black)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        self.setFont(f)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(QColor(glow_color or theme.ACCENT))
        self._glow.setOffset(0, 3)
        self._glow.setBlurRadius(20)
        self.setGraphicsEffect(self._glow)
        self._hovering = False

        self._hover_anim = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._hover_anim.setDuration(160)

        # gentle idle breathing so the button feels alive at rest
        self._breathe = QPropertyAnimation(self._glow, b"blurRadius", self)
        self._breathe.setStartValue(16)
        self._breathe.setKeyValueAt(0.5, 26)
        self._breathe.setEndValue(16)
        self._breathe.setDuration(2600)
        self._breathe.setLoopCount(-1)
        self._breathe.start()

    def _flare(self, target):
        self._breathe.stop()
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._glow.blurRadius())
        self._hover_anim.setEndValue(target)
        self._hover_anim.start()

    def enterEvent(self, e):
        self._hovering = True
        if self.isEnabled():
            self._flare(40)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hovering = False
        self._hover_anim.stop()
        if self.isEnabled():
            self._breathe.start()
        super().leaveEvent(e)

    def setEnabled(self, on):
        super().setEnabled(on)
        self._glow.setEnabled(on)
        if on and not self._hovering:
            self._breathe.start()
        else:
            self._breathe.stop()


def scan_worlds(save_dir: str) -> list[str]:
    """World names (= .sav stems) found in a save folder."""
    folder = Path(save_dir) if save_dir else None
    names: list[str] = []
    if folder and folder.exists():
        seen = set()
        for p in sorted(folder.glob("*.sav")):
            if p.stem not in seen:
                seen.add(p.stem)
                names.append(p.stem)
    return names


class WorldField(QWidget):
    """Label + editable combo listing the worlds found in the save folder."""

    def __init__(self, label="World", value="", hint="", parent=None):
        super().__init__(parent)
        from PySide6.QtWidgets import QComboBox
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)
        lab = QLabel(label)
        lab.setProperty("role", "fieldLabel")
        box.addWidget(lab)
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setFixedHeight(38)
        self.combo.setCurrentText(value)
        box.addWidget(self.combo)
        self.note = QLabel(hint)
        self.note.setProperty("role", "hint")
        self.note.setWordWrap(True)
        self.note.setVisible(bool(hint))
        self._hint = hint
        box.addWidget(self.note)

    def refresh(self, save_dir: str, keep_current=True):
        current = self.combo.currentText().strip()
        names = scan_worlds(save_dir)
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItems(names)
        if keep_current and current:
            self.combo.setCurrentText(current)
        elif names:
            self.combo.setCurrentText(names[0])
        else:
            self.combo.setCurrentText("")
        self.combo.blockSignals(False)
        return names

    def value(self) -> str:
        return self.combo.currentText().strip()

    def set_error(self, message):
        self.note.setText(message)
        self.note.setProperty("role", "error")
        self.note.setVisible(True)
        self.note.style().unpolish(self.note)
        self.note.style().polish(self.note)

    def clear_error(self):
        self.note.setText(self._hint)
        self.note.setProperty("role", "hint")
        self.note.setVisible(bool(self._hint))
        self.note.style().unpolish(self.note)
        self.note.style().polish(self.note)


class FormField(QWidget):
    """Label + line edit (+ optional Browse) + hint/error line."""

    def __init__(self, label, value="", hint="", browse=None, placeholder="", parent=None):
        """`browse`: None, 'dir', or 'file' — adds a Browse button."""
        super().__init__(parent)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(6)

        lab = QLabel(label)
        lab.setProperty("role", "fieldLabel")
        box.addWidget(lab)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.edit = QLineEdit(value)
        self.edit.setPlaceholderText(placeholder)
        self.edit.setFixedHeight(38)
        row.addWidget(self.edit, 1)
        if browse:
            btn = make_button("Browse", "ghost", height=38)
            btn.clicked.connect(lambda: self._browse(browse))
            row.addWidget(btn)
        box.addLayout(row)

        self.note = QLabel(hint)
        self.note.setProperty("role", "hint")
        self.note.setWordWrap(True)
        self.note.setVisible(bool(hint))
        self._hint = hint
        box.addWidget(self.note)

    def _browse(self, kind):
        start = self.edit.text().strip() or str(Path.home())
        if kind == "dir":
            chosen = QFileDialog.getExistingDirectory(self, "Choose a folder", start)
        else:
            chosen, _ = QFileDialog.getOpenFileName(
                self, "Choose a file", start, "Programs (*.exe);;All files (*.*)")
        if chosen:
            self.edit.setText(chosen)
            self.clear_error()
            self.edit.editingFinished.emit()

    def value(self) -> str:
        return self.edit.text().strip()

    def set_error(self, message):
        self.note.setText(message)
        self.note.setProperty("role", "error")
        self.note.setVisible(True)
        self.edit.setProperty("invalid", "true")
        self._repolish()

    def clear_error(self):
        self.note.setText(self._hint)
        self.note.setProperty("role", "hint")
        self.note.setVisible(bool(self._hint))
        self.edit.setProperty("invalid", "false")
        self._repolish()

    def _repolish(self):
        for w in (self.note, self.edit):
            w.style().unpolish(w)
            w.style().polish(w)
