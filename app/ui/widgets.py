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


class Avatar(QWidget):
    """Colored circle for the activity feed: initials, or a chosen emoji."""

    def __init__(self, name: str, size=30, emoji="", color=None, parent=None):
        super().__init__(parent)
        self._name = name or "?"
        self._emoji = emoji or ""
        self._color = color or None
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
    """The showpiece action: emerald gradient with a glow that breathes at
    rest and flares on hover."""

    def __init__(self, text="PLAY", parent=None):
        super().__init__(text, parent)
        self.setProperty("variant", "primary")
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(60)
        f = QFont(self.font())
        f.setPointSizeF(12.5)
        f.setWeight(QFont.Black)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 2.0)
        self.setFont(f)
        self._glow = QGraphicsDropShadowEffect(self)
        self._glow.setColor(QColor(theme.ACCENT))
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
