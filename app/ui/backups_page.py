"""Backup browser: every safety net the sync core has woven, restorable."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QInputDialog, QLabel,
                               QLineEdit, QScrollArea, QVBoxLayout, QWidget)

from ..core.backups import BackupInfo
from . import icons, theme, widgets


def _pretty_label(label: str) -> str:
    if label.startswith("local_v"):
        return f"Your save, before pulling a newer one (was v{label[7:]})"
    if label.startswith("shared_v"):
        return f"A friend's session you replaced (v{label[8:]})"
    if label.startswith("group_v"):
        return f"v{label[7:]} — kept in the shared folder for everyone"
    if label == "pre_restore":
        return "Automatic copy taken before a restore"
    if label == "session":
        return "After a play session"
    return label


class BackupsPage(QWidget):
    back_requested = Signal()
    restore_requested = Signal(object)     # BackupInfo
    checkpoint_requested = Signal(str)     # name
    delete_requested = Signal(object)      # BackupInfo (checkpoint)

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
        self.checkpoint_btn = widgets.make_button("New checkpoint", "ghost",
                                                  "flag", height=32)
        self.checkpoint_btn.clicked.connect(self._new_checkpoint)
        header.addWidget(self.checkpoint_btn)
        root.addLayout(header)
        root.addSpacing(6)

        intro = QLabel("Checkpoints are snapshots you name and keep. Auto-backups "
                       "are taken whenever a save would be overwritten. Restoring "
                       "brings one back to this PC — share it afterwards if the "
                       "whole group should return to it.")
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

    def _new_checkpoint(self):
        name, ok = QInputDialog.getText(
            self, "New checkpoint", "Name this snapshot of your current save:",
            QLineEdit.Normal, "Before the dragon")
        if ok and name.strip():
            self.checkpoint_requested.emit(name.strip())

    def load(self, world_name: str, checkpoints: list[BackupInfo],
             backups: list[BackupInfo], group_history: list[BackupInfo] = ()):
        self.title.setText(f"Backups — {world_name}")
        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not checkpoints and not backups and not group_history:
            empty = QLabel("Nothing here yet. Make a checkpoint before something "
                           "risky, or let auto-backups build up as you play.")
            empty.setWordWrap(True)
            empty.setAlignment(Qt.AlignCenter)
            empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px;"
                                f"padding: 26px;")
            self.box.addWidget(empty)
            self.box.addStretch(1)
            return

        first = True
        if checkpoints:
            self.box.addWidget(self._subhead("CHECKPOINTS", first=first))
            first = False
            for info in checkpoints:
                self.box.addWidget(self._row(info))
        if group_history:
            self.box.addWidget(self._subhead("GROUP HISTORY (SHARED FOLDER)",
                                             first=first))
            first = False
            for info in group_history:
                self.box.addWidget(self._row(info))
        if backups:
            self.box.addWidget(self._subhead("AUTO-BACKUPS", first=first))
            for info in backups:
                self.box.addWidget(self._row(info))
        self.box.addStretch(1)

    def _subhead(self, text, first=False):
        lbl = QLabel(text)
        lbl.setObjectName("SectionLabel")
        lbl.setContentsMargins(6, 4 if first else 14, 0, 6)
        return lbl

    def _row(self, info: BackupInfo, first=False):
        row = QWidget()
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 10, 6, 10)
        lay.setSpacing(10)

        ic = QLabel()
        ic.setPixmap(icons.pixmap("flag" if info.is_checkpoint else "clock",
                                  theme.EMBER if info.is_checkpoint else theme.TEXT_FAINT, 18))
        ic.setStyleSheet("border: none;")
        lay.addWidget(ic, 0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(2)
        heading = info.name if info.is_checkpoint else _pretty_label(info.label)
        title = QLabel(heading)
        title.setStyleSheet("border: none; font-size: 12.5px; font-weight: 600;")
        title.setWordWrap(True)
        when = info.stamp.strftime("%a %d %b, %H:%M") if info.stamp else "unknown time"
        meta = QLabel(f"{when} · {info.file_count} file{'s' if info.file_count != 1 else ''}")
        meta.setStyleSheet(f"border: none; color: {theme.TEXT_FAINT}; font-size: 11.5px;")
        col.addWidget(title)
        col.addWidget(meta)
        lay.addLayout(col, 1)

        if info.is_checkpoint:
            delete = widgets.icon_button("trash", theme.TEXT_FAINT,
                                         tooltip="Delete checkpoint")
            delete.clicked.connect(lambda _=False, i=info: self.delete_requested.emit(i))
            lay.addWidget(delete, 0, Qt.AlignVCenter)
        restore = widgets.make_button("Restore", "ghost", "rotate-ccw", height=30)
        restore.clicked.connect(lambda _=False, i=info: self.restore_requested.emit(i))
        lay.addWidget(restore, 0, Qt.AlignVCenter)
        return row
