"""'Test my setup' — a friendly checklist that catches setup snags."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from ..core import preflight
from . import icons, theme, widgets

_STATUS_STYLE = {
    preflight.OK:   (theme.ACCENT, "check-circle"),
    preflight.WARN: (theme.AMBER, "alert"),
    preflight.FAIL: (theme.RED_HOVER, "x"),
}


class PreflightPage(QWidget):
    back_requested = Signal()
    run_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        title = QLabel("Test my setup")
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(6)

        intro = QLabel("A quick check that everything's wired up so your saves "
                       "actually reach your friends.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        root.addWidget(intro)
        root.addSpacing(12)

        self.summary = QLabel("")
        self.summary.setWordWrap(True)
        self.summary.setVisible(False)
        root.addWidget(self.summary)
        root.addSpacing(6)

        card = QFrame()
        card.setObjectName("Card")
        wrap = QVBoxLayout(card)
        wrap.setContentsMargins(6, 6, 6, 6)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(10, 8, 10, 8)
        self.box.setSpacing(0)
        scroll.setWidget(self.body)
        wrap.addWidget(scroll)
        root.addWidget(card, 1)
        root.addSpacing(12)

        run_row = QHBoxLayout()
        run_row.addStretch(1)
        self.run_btn = widgets.make_button("Run the check", "primary", "refresh", height=40)
        self.run_btn.setMinimumWidth(150)
        self.run_btn.clicked.connect(self.run_requested.emit)
        run_row.addWidget(self.run_btn)
        root.addLayout(run_row)

        self._placeholder()

    def _placeholder(self):
        self._clear()
        msg = QLabel("Hit “Run the check” to test everything.")
        msg.setAlignment(Qt.AlignCenter)
        msg.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px; padding: 28px;")
        self.box.addWidget(msg)
        self.box.addStretch(1)

    def _clear(self):
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def set_running(self):
        self.run_btn.setEnabled(False)
        self.run_btn.setText("Checking…")
        self.summary.setVisible(False)

    def show_results(self, checks):
        self.run_btn.setEnabled(True)
        self.run_btn.setText("Run again")
        self._clear()
        for i, c in enumerate(checks):
            self.box.addWidget(self._row(c, first=(i == 0)))
        self.box.addStretch(1)

        worst = preflight.worst(checks)
        if worst == preflight.OK:
            self.summary.setText("✓  Everything's ready. You're good to play.")
            self.summary.setStyleSheet(f"color: {theme.ACCENT}; font-size: 13px; font-weight: 600;")
        elif worst == preflight.WARN:
            self.summary.setText("Mostly good — a couple of things worth a look below.")
            self.summary.setStyleSheet(f"color: {theme.AMBER}; font-size: 13px; font-weight: 600;")
        else:
            self.summary.setText("Something needs fixing before your saves will sync.")
            self.summary.setStyleSheet(f"color: {theme.RED_HOVER}; font-size: 13px; font-weight: 600;")
        self.summary.setVisible(True)

    def _row(self, check, first=False):
        row = QWidget()
        if not first:
            row.setStyleSheet(f"border-top: 1px solid {theme.BORDER_SOFT};")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(11)
        color, icon_name = _STATUS_STYLE.get(check.status, _STATUS_STYLE[preflight.WARN])
        ic = QLabel()
        ic.setPixmap(icons.pixmap(icon_name, color, 18))
        ic.setStyleSheet("border: none;")
        lay.addWidget(ic, 0, Qt.AlignTop)
        col = QVBoxLayout()
        col.setSpacing(2)
        label = QLabel(check.label)
        label.setStyleSheet("border: none; font-size: 13px; font-weight: 600;")
        detail = QLabel(check.detail)
        detail.setWordWrap(True)
        detail.setStyleSheet(f"border: none; color: {theme.TEXT_DIM}; font-size: 12px;")
        col.addWidget(label)
        col.addWidget(detail)
        lay.addLayout(col, 1)
        return row
