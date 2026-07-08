"""The one blocking dialog in the app: an unmissable overwrite confirmation.

Dim the whole window, present exactly two choices, default focus on the safe
one. Used for pull-conflicts, stale pushes, and quitting mid-game.
"""

from PySide6.QtCore import QEventLoop, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget)

from . import icons, theme, widgets


class ConfirmOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.hide()
        self._loop = None
        self._answer = False
        parent.installEventFilter(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.addStretch(1)

        self.card = QFrame(self)
        self.card.setObjectName("Card")
        self.card.setStyleSheet(
            f"#Card {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER};"
            f"border-radius: 14px; }}")
        card_box = QVBoxLayout(self.card)
        card_box.setContentsMargins(24, 22, 24, 20)
        card_box.setSpacing(10)

        head = QHBoxLayout()
        head.setSpacing(10)
        self.icon_label = QLabel()
        self.icon_label.setPixmap(icons.pixmap("alert", theme.AMBER, 22))
        self.icon_label.setStyleSheet("background: transparent; border: none;")
        head.addWidget(self.icon_label, 0, Qt.AlignTop)
        self.title_label = QLabel()
        self.title_label.setWordWrap(True)
        self.title_label.setStyleSheet(
            "background: transparent; border: none; font-size: 15px; font-weight: 600;")
        head.addWidget(self.title_label, 1)
        card_box.addLayout(head)

        self.body_label = QLabel()
        self.body_label.setWordWrap(True)
        self.body_label.setStyleSheet(
            f"background: transparent; border: none; color: {theme.TEXT_DIM};"
            f"font-size: 12.5px; line-height: 150%;")
        card_box.addWidget(self.body_label)

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        buttons.addStretch(1)
        self.safe_btn = widgets.make_button("Keep my progress", "ghost", height=38)
        self.danger_btn = widgets.make_button("Overwrite", "danger", height=38)
        self.safe_btn.clicked.connect(lambda: self._finish(False))
        self.danger_btn.clicked.connect(lambda: self._finish(True))
        buttons.addWidget(self.safe_btn)
        buttons.addWidget(self.danger_btn)
        card_box.addSpacing(6)
        card_box.addLayout(buttons)

        outer.addWidget(self.card)
        outer.addStretch(1)

    def eventFilter(self, obj, e):
        if obj is self.parent() and e.type() == e.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(5, 9, 13, 205))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(False)
        else:
            super().keyPressEvent(e)

    def ask(self, title, body, danger_label="Overwrite", safe_label="Keep my progress") -> bool:
        """Show the overlay and block (on a nested event loop) until answered."""
        self.title_label.setText(title)
        self.body_label.setText(body)
        self.danger_btn.setText(danger_label)
        self.safe_btn.setText(safe_label)
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.safe_btn.setFocus()
        self._loop = QEventLoop(self)
        self._loop.exec()
        return self._answer

    def _finish(self, answer):
        self._answer = answer
        self.hide()
        if self._loop:
            self._loop.quit()
            self._loop = None
