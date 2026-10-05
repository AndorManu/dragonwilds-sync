"""Two small asks about anonymous reports.

Consent: asked once, both answers equally easy, nothing is sent before a yes.
Feedback: after a game's first successful share, "did it work?" with a thumbs
up or down and an optional line. That's the signal that moves a beta game to
tested.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout,
                               QWidget)

from . import theme, widgets


class ReportOverlay(QWidget):
    consent_given = Signal(bool)
    feedback_given = Signal(str, str, str)     # game_id, "up"|"down", comment
    tip_answer = Signal(str)                   # "tip" | "later" | "never"

    def __init__(self, parent):
        super().__init__(parent)
        self.hide()
        self._mode = None
        self._game_id = None
        self._rating = None
        parent.installEventFilter(self)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 32, 32, 32)
        outer.addStretch(1)
        self.card = QFrame()
        self.card.setObjectName("ReportCard")
        box = QVBoxLayout(self.card)
        box.setContentsMargins(24, 20, 24, 18)
        box.setSpacing(10)

        self.title = QLabel("")
        self.title.setWordWrap(True)
        self.title.setStyleSheet("background: transparent; border: none;"
                                 "font-size: 15px; font-weight: 650;")
        box.addWidget(self.title)
        self.body = QLabel("")
        self.body.setWordWrap(True)
        self.body.setStyleSheet(f"background: transparent; border: none;"
                                f"color: {theme.TEXT_DIM}; font-size: 12px;")
        box.addWidget(self.body)

        # feedback: thumbs + optional comment
        self.thumbs = QWidget()
        self.thumbs.setStyleSheet("background: transparent;")
        trow = QHBoxLayout(self.thumbs)
        trow.setContentsMargins(0, 2, 0, 0)
        trow.setSpacing(8)
        self.up_btn = widgets.make_button("👍  It worked", "ghost", height=38)
        self.down_btn = widgets.make_button("👎  Something's off", "ghost", height=38)
        self.up_btn.clicked.connect(lambda: self._pick("up"))
        self.down_btn.clicked.connect(lambda: self._pick("down"))
        trow.addWidget(self.up_btn, 1)
        trow.addWidget(self.down_btn, 1)
        box.addWidget(self.thumbs)
        self.comment = QLineEdit()
        self.comment.setPlaceholderText("Anything that went wrong or felt confusing? (optional)")
        self.comment.setMaxLength(500)
        self.comment.setFixedHeight(38)
        box.addWidget(self.comment)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.no_btn = widgets.make_button("No thanks", "ghost", height=36)
        self.yes_btn = widgets.make_button("Share anonymous reports", "primary", height=36)
        self.no_btn.clicked.connect(lambda: self._finish(False))
        self.yes_btn.clicked.connect(lambda: self._finish(True))
        buttons.addWidget(self.no_btn)
        buttons.addSpacing(8)
        buttons.addWidget(self.yes_btn)
        box.addLayout(buttons)
        self.never_btn = widgets.make_button("Don't ask again", "subtle", height=26)
        self.never_btn.clicked.connect(self._never)
        box.addWidget(self.never_btn, 0, Qt.AlignRight)

        outer.addWidget(self.card)
        outer.addStretch(1)

    # -- plumbing ----------------------------------------------------------------
    def eventFilter(self, obj, e):
        if obj is self.parent() and e.type() == e.Type.Resize:
            self.setGeometry(self.parent().rect())
        return False

    def paintEvent(self, e):
        QPainter(self).fillRect(self.rect(), QColor(5, 9, 13, 185))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Escape:
            self._finish(False)
        else:
            super().keyPressEvent(e)

    def _style(self):
        self.card.setStyleSheet(
            f"#ReportCard {{ background: {theme.SURFACE_2}; border: 1px solid {theme.BORDER};"
            f"border-radius: 14px; }}")

    def _show(self):
        self._style()
        self.yes_btn.setMinimumWidth(self.yes_btn.fontMetrics().horizontalAdvance(
            self.yes_btn.text()) + 64)
        self.setGeometry(self.parent().rect())
        self.show()
        self.raise_()

    # -- the two asks ------------------------------------------------------------
    def ask_consent(self):
        self._mode = "consent"
        self.title.setText("Help WorldSync work for every game?")
        self.body.setText(
            "If you say yes, WorldSync sends short anonymous reports: which game, whether "
            "a share or pull worked, and the app version. That's how new games get "
            "fixed and marked as tested.\n\n"
            "Never sent: your name, world names, folders, invite codes or saves. "
            "You can switch it off any time in Settings.")
        self.thumbs.hide()
        self.comment.hide()
        self.never_btn.hide()
        self.no_btn.setText("No thanks")
        self.yes_btn.setText("Share anonymous reports")
        self.yes_btn.show()
        self._show()
        self.no_btn.setFocus()

    def ask_feedback(self, game_id: str, game_name: str):
        self._mode = "feedback"
        self._game_id = game_id
        self._rating = None
        self.title.setText(f"Did WorldSync work for {game_name}?")
        self.body.setText("Your first share went through. One click tells me whether "
                          "the whole thing worked the way it should.")
        self.thumbs.show()
        self.never_btn.hide()
        self.comment.clear()
        self.comment.show()
        for b in (self.up_btn, self.down_btn):
            b.setStyleSheet("")
        self.no_btn.setText("Skip")
        self.yes_btn.setText("Send")
        self.yes_btn.setEnabled(False)
        self._show()

    def ask_tip(self, shares: int):
        self._mode = "tip"
        self.title.setText("Enjoying WorldSync?")
        self.body.setText(
            f"Your group has shared {shares} sessions without renting a server. WorldSync "
            "is free and stays free, it's built by one person in their spare time. If it "
            "saved you a server bill, a coffee keeps new games coming.")
        self.thumbs.hide()
        self.comment.hide()
        self.never_btn.show()
        self.no_btn.setText("Maybe later")
        self.yes_btn.setText("Buy me a coffee")
        self._show()
        self.no_btn.setFocus()

    def _never(self):
        self.hide()
        self.tip_answer.emit("never")

    def _pick(self, rating):
        self._rating = rating
        self.yes_btn.setEnabled(True)
        for b, r in ((self.up_btn, "up"), (self.down_btn, "down")):
            b.setStyleSheet(
                f"QPushButton {{ border: 1.5px solid {theme.ACCENT}; color: {theme.ACCENT};"
                f"background: {theme.SURFACE}; }}" if r == rating else "")

    def _finish(self, yes: bool):
        mode = self._mode
        self.hide()
        self.yes_btn.setEnabled(True)
        if mode == "consent":
            self.consent_given.emit(yes)
        elif mode == "tip":
            self.tip_answer.emit("tip" if yes else "later")
        elif mode == "feedback" and yes and self._rating:
            self.feedback_given.emit(self._game_id, self._rating, self.comment.text().strip())
