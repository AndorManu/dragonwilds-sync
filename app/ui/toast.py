"""Non-blocking toast notifications, stacked at the bottom of the window.

The host widget hugs its content so the rest of the UI stays clickable while
toasts are visible. Click a toast to dismiss it early.
"""

from PySide6.QtCore import QPropertyAnimation, Qt, QTimer
from PySide6.QtWidgets import (QFrame, QGraphicsOpacityEffect, QHBoxLayout,
                               QLabel, QVBoxLayout, QWidget)

from . import icons, theme

KIND_STYLE = {
    "success": (theme.ACCENT, "check-circle"),
    "info":    (theme.TEXT_DIM, "info"),
    "warning": (theme.AMBER, "alert"),
    "error":   (theme.RED_HOVER, "alert"),
}

TOAST_LIFETIME_MS = 4600
SIDE_MARGIN = 22
BOTTOM_MARGIN = 20


class Toast(QFrame):
    def __init__(self, kind, text, host):
        super().__init__(host)
        self._host = host
        color, icon_name = KIND_STYLE.get(kind, KIND_STYLE["info"])
        self.setStyleSheet(
            f"Toast {{ background: {theme.SURFACE_2};"
            f"border: 1px solid {theme.BORDER};"
            f"border-left: 3px solid {color};"
            f"border-radius: 10px; }}"
        )
        self.setCursor(Qt.PointingHandCursor)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 10, 14, 10)
        row.setSpacing(10)
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 16))
        ic.setStyleSheet("background: transparent; border: none;")
        row.addWidget(ic, 0, Qt.AlignTop)
        label = QLabel(text)
        label.setWordWrap(True)
        label.setStyleSheet(
            f"background: transparent; border: none; color: {theme.TEXT}; font-size: 12.5px;")
        row.addWidget(label, 1)

        self._fx = QGraphicsOpacityEffect(self)
        self._fx.setOpacity(0.0)
        self.setGraphicsEffect(self._fx)

    def mousePressEvent(self, e):
        self._host.dismiss(self)


class ToastHost(QWidget):
    """Bottom-anchored stack that grows and shrinks with its toasts."""

    def __init__(self, parent):
        super().__init__(parent)
        self._box = QVBoxLayout(self)
        self._box.setContentsMargins(0, 0, 0, 0)
        self._box.setSpacing(8)
        self.hide()
        parent.installEventFilter(self)

    def eventFilter(self, obj, e):
        if obj is self.parent() and e.type() == e.Type.Resize:
            self._reposition()
        return False

    def _reposition(self):
        parent = self.parent()
        width = parent.width() - 2 * SIDE_MARGIN
        self.setFixedWidth(width)
        self.adjustSize()
        self.move(SIDE_MARGIN, parent.height() - self.height() - BOTTOM_MARGIN)

    def show_toast(self, kind, text):
        toast = Toast(kind, text, self)
        self._box.addWidget(toast)
        self.show()
        self.raise_()
        self._reposition()

        fade = QPropertyAnimation(toast._fx, b"opacity", toast)
        fade.setDuration(220)
        fade.setStartValue(0.0)
        fade.setEndValue(1.0)
        fade.start(QPropertyAnimation.DeleteWhenStopped)

        QTimer.singleShot(TOAST_LIFETIME_MS, lambda: self.dismiss(toast))

    def dismiss(self, toast):
        try:
            if toast.parent() is not self:
                return
        except RuntimeError:   # already deleted (clicked away before the timer)
            return
        fade = QPropertyAnimation(toast._fx, b"opacity", toast)
        fade.setDuration(170)
        fade.setStartValue(toast._fx.opacity())
        fade.setEndValue(0.0)

        def cleanup():
            self._box.removeWidget(toast)
            toast.setParent(None)
            toast.deleteLater()
            if self._box.count() == 0:
                self.hide()
            else:
                self._reposition()

        fade.finished.connect(cleanup)
        fade.start(QPropertyAnimation.DeleteWhenStopped)
