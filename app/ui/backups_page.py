"""Backup browser: every safety net the sync core has woven, restorable."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from ..core.backups import BackupInfo
from . import icons, theme, widgets


def _pretty_label(label: str) -> str:
    if label.startswith("local_v"):
        return f"Your save, before pulling a newer one (was v{label[7:]})"
    if label.startswith("shared_v"):
        return f"A friend's session you replaced (v{label[8:]})"
    if label == "pre_restore":
        return "Automatic copy taken before a restore"
    return label


class BackupsPage(QWidget):
    back_requested = Signal()
    restore_requested = Signal(object)     # BackupInfo

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        self.title = QLabel("Backups")
        self.title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(self.title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(6)

        intro = QLabel("Whenever a save is about to be replaced, a copy lands "
                       "here first. Restoring brings one back to this PC — "
                       "share it afterwards if the whole group should return to it.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        root.addWidget(intro)
        root.addSpacing(12)

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

    def load(self, world_name: str, backups: list[BackupInfo]):
        self.title.setText(f"Backups — {world_name}")
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not backups:
            empty = QLabel("No backups yet. They appear automatically the first "
                           "time a save would be overwritten.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px;"
                                f"padding: 26px;")
            self.box.addWidget(empty)
            self.box.addStretch(1)
            return

        for i, info in enumerate(backups):
            self.box.addWidget(self._row(info, first=(i == 0)))
        self.box.addStretch(1)

    def _row(self, info: BackupInfo, first=False):
        row = QWidget()
        if not first:
            row.setStyleSheet(f"border-top: 1px solid {theme.BORDER_SOFT};")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(icons.pixmap("clock", theme.TEXT_FAINT, 18))
        ic.setStyleSheet("border: none;")
        lay.addWidget(ic, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(2)
        title = QLabel(_pretty_label(info.label))
        title.setStyleSheet("border: none; font-size: 12.5px; font-weight: 600;")
        title.setWordWrap(True)
        when = info.stamp.strftime("%a %d %b, %H:%M") if info.stamp else "unknown time"
        meta = QLabel(f"{when} · {info.file_count} file{'s' if info.file_count != 1 else ''}")
        meta.setStyleSheet(f"border: none; color: {theme.TEXT_FAINT}; font-size: 11.5px;")
        col.addWidget(title)
        col.addWidget(meta)
        lay.addLayout(col, 1)

        restore = widgets.make_button("Restore", "ghost", "rotate-ccw", height=30)
        restore.clicked.connect(lambda _=False, i=info: self.restore_requested.emit(i))
        lay.addWidget(restore, 0, Qt.AlignVCenter)
        return row
