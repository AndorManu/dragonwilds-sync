"""Settings: edit the onboarding choices, plus log access."""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QVBoxLayout, QWidget)

from ..core import paths
from . import theme, widgets


class SettingsPage(QWidget):
    saved = Signal(dict)
    cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.cancelled.emit)
        header.addWidget(back)
        title = QLabel("Settings")
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(14)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        form = QVBoxLayout(body)
        form.setContentsMargins(2, 2, 10, 2)
        form.setSpacing(16)

        self.name_field = widgets.FormField("Your name")
        self.save_dir_field = widgets.FormField("Dragonwilds save folder", browse="dir")
        self.save_dir_field.edit.editingFinished.connect(self._rescan)
        self.world_field = widgets.WorldField("World to sync")
        self.shared_field = widgets.FormField(
            "Shared folder", browse="dir",
            hint="Everyone in the group must point at the same cloud-synced folder.")
        self.exe_field = widgets.FormField(
            "Game executable (optional)", browse="file",
            hint="Leave empty to launch through Steam — that's right for almost everyone.")
        for f in (self.name_field, self.save_dir_field, self.world_field,
                  self.shared_field, self.exe_field):
            form.addWidget(f)

        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {theme.BORDER_SOFT};")
        form.addSpacing(4)
        form.addWidget(divider)

        logs_btn = widgets.make_button("Open log folder", "subtle", "external", height=32)
        logs_btn.clicked.connect(self._open_logs)
        row = QHBoxLayout()
        row.addWidget(logs_btn)
        row.addStretch(1)
        form.addLayout(row)

        cap = QLabel(f"Settings are stored per-player at {paths.APP_DIR}")
        cap.setProperty("role", "hint")
        cap.setWordWrap(True)
        form.addWidget(cap)
        form.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)
        root.addSpacing(12)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = widgets.make_button("Cancel", "ghost", height=40)
        cancel.clicked.connect(self.cancelled.emit)
        save = widgets.make_button("Save changes", "primary", height=40)
        save.setMinimumWidth(140)
        save.clicked.connect(self._submit)
        buttons.addWidget(cancel)
        buttons.addSpacing(8)
        buttons.addWidget(save)
        root.addLayout(buttons)

    def load(self, cfg: dict):
        cfg = cfg or {}
        self.name_field.edit.setText(cfg.get("player_name", ""))
        self.save_dir_field.edit.setText(cfg.get("local_save_dir", str(paths.DEFAULT_SAVE_DIR)))
        self.shared_field.edit.setText(cfg.get("sync_dir", ""))
        self.exe_field.edit.setText(cfg.get("exe_path") or "")
        self.world_field.refresh(self.save_dir_field.value(), keep_current=False)
        self.world_field.combo.setCurrentText(cfg.get("world_name", ""))
        for f in (self.name_field, self.save_dir_field, self.shared_field, self.exe_field):
            f.clear_error()
        self.world_field.clear_error()

    def _rescan(self):
        self.world_field.refresh(self.save_dir_field.value())

    def _open_logs(self):
        paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(paths.LOG_DIR))  # noqa: S606

    def _submit(self):
        ok = True
        if not self.name_field.value():
            self.name_field.set_error("A name is required.")
            ok = False
        if not self.save_dir_field.value():
            self.save_dir_field.set_error("The game's save folder is required.")
            ok = False
        if not self.world_field.value():
            self.world_field.set_error("A world name is required.")
            ok = False
        if not self.shared_field.value():
            self.shared_field.set_error("The shared folder is required.")
            ok = False
        exe = self.exe_field.value()
        if exe and not os.path.isfile(exe):
            self.exe_field.set_error("That file doesn't exist — leave empty to use Steam.")
            ok = False
        if not ok:
            return
        self.saved.emit({
            "player_name": self.name_field.value(),
            "local_save_dir": self.save_dir_field.value(),
            "world_name": self.world_field.value(),
            "sync_dir": self.shared_field.value(),
            "exe_path": exe or None,
            "steam_app_id": paths.STEAM_APP_ID,
        })
