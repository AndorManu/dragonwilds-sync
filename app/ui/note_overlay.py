"""Post-session note prompt: one optional line for the world's story."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from . import theme, widgets

AUTO_SKIP_MS = 60_000


class NoteOverlay(QWidget):
    submitted = Signal(str, int, str)      # world_id, version, note

    def __init__(self, parent):
        super().__init__(parent)
        self.hide()
        self._world_id = None
        self._version = None
        parent.installEventFilter(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(36, 36, 36, 36)
        outer.addStretch(1)

        card = QFrame()
        card.setStyleSheet(
            f"QFrame {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER};"
            f"border-radius: 14px; }}")
        box = QVBoxLayout(card)
        box.setContentsMargins(24, 20, 24, 18)
        box.setSpacing(10)

        title = QLabel("How was the session?")
        title.setStyleSheet("background: transparent; border: none;"
                            "font-size: 15px; font-weight: 650;")
        box.addWidget(title)
        sub = QLabel("One line for the world's story — your friends see it in the feed.")
        sub.setWordWrap(True)
        sub.setStyleSheet(f"background: transparent; border: none;"
                          f"color: {theme.TEXT_DIM}; font-size: 12px;")
        box.addWidget(sub)

        self.edit = QLineEdit()
        self.edit.setPlaceholderText("e.g. Built the gatehouse, found the swamp cave…")
        self.edit.setFixedHeight(38)
        self.edit.setMaxLength(200)
        self.edit.returnPressed.connect(self._submit)
        box.addWidget(self.edit)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        skip = widgets.make_button("Skip", "ghost", height=34)
        skip.clicked.connect(self._skip)
        add = widgets.make_button("Add note", "primary", height=34)
        add.setMinimumWidth(110)
        add.clicked.connect(self._submit)
        buttons.addWidget(skip)
        buttons.addSpacing(8)
        buttons.addWidget(add)
        box.addLayout(buttons)

        outer.addWidget(card)
        outer.addStretch(1)

        self._auto_skip = QTimer(self)
        self._auto_skip.setSingleShot(True)
        self._auto_skip.setInterval(AUTO_SKIP_MS)
        self._auto_skip.timeout.connect(self._skip)

    def eventFilter(self, obj, e):
        if obj is self.parent() and e.type() == e.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def paintEvent(self, e):
        p = QPainter(self)
        p.fillRect(self.rect(), QColor(5, 9, 13, 185))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._skip()
        else:
            super().keyPressEvent(e)

    def open(self, world_id: str, version: int):
        self._world_id = world_id
        self._version = version
        self.edit.clear()
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()
        self.edit.setFocus()
        self._auto_skip.start()

    def _submit(self):
        note = self.edit.text().strip()
        self._auto_skip.stop()
        self.hide()
        if note and self._world_id is not None:
            self.submitted.emit(self._world_id, self._version, note)

    def _skip(self):
        self._auto_skip.stop()
        self.hide()
