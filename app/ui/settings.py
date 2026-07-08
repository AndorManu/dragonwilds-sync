"""Settings: profile, game, active world, and app behavior — one calm page."""

import os

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from ..core import autostart, paths, steam
from . import icons, theme, widgets

EMOJI_CHOICES = ["", "🐉", "⚔️", "🛡️", "🏹", "🔥", "🌿", "🍺", "👑", "🧙", "🪓", "🦴"]


class SettingsPage(QWidget):
    saved = Signal(dict, dict)     # global fields, world fields (active world)
    cancelled = Signal()
    remove_world_requested = Signal(str)   # world_id
    about_requested = Signal()
    preflight_requested = Signal()
    publish_update_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._world_id = None
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
        root.addSpacing(10)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        form = QVBoxLayout(body)
        form.setContentsMargins(2, 2, 10, 2)
        form.setSpacing(14)

        # -- profile ------------------------------------------------------------
        form.addWidget(self._section("YOU"))
        self.name_field = widgets.FormField("Your name")
        form.addWidget(self.name_field)

        flair_row = QHBoxLayout()
        flair_row.setSpacing(10)
        emoji_col = QVBoxLayout()
        emoji_col.setSpacing(6)
        emoji_label = QLabel("Emblem")
        emoji_label.setProperty("role", "fieldLabel")
        emoji_col.addWidget(emoji_label)
        self.emoji_combo = QComboBox()
        self.emoji_combo.setFixedHeight(38)
        for e in EMOJI_CHOICES:
            self.emoji_combo.addItem(e if e else "None")
        emoji_col.addWidget(self.emoji_combo)
        flair_row.addLayout(emoji_col, 1)

        color_col = QVBoxLayout()
        color_col.setSpacing(6)
        color_label = QLabel("Color")
        color_label.setProperty("role", "fieldLabel")
        color_col.addWidget(color_label)
        self.color_combo = QComboBox()
        self.color_combo.setFixedHeight(38)
        self.color_combo.addItem("Auto")
        for c in theme.AVATAR_COLORS:
            self.color_combo.addItem(self._swatch(c), "")
        color_col.addWidget(self.color_combo)
        flair_row.addLayout(color_col, 1)
        form.addLayout(flair_row)
        flair_hint = QLabel("Shown next to your name in everyone's session feed.")
        flair_hint.setProperty("role", "hint")
        form.addWidget(flair_hint)

        # -- game ----------------------------------------------------------------
        form.addWidget(self._section("GAME"))
        self.save_dir_field = widgets.FormField("Dragonwilds save folder", browse="dir")
        self.save_dir_field.edit.editingFinished.connect(self._rescan)
        form.addWidget(self.save_dir_field)

        self.exe_field = widgets.FormField(
            "Game executable (optional)", browse="file",
            hint="Leave empty to launch through Steam — that's right for almost everyone.")
        form.addWidget(self.exe_field)
        detect_row = QHBoxLayout()
        detect_btn = widgets.make_button("Auto-detect install", "subtle", height=30)
        detect_btn.clicked.connect(self._detect_exe)
        detect_row.addWidget(detect_btn)
        self.detect_result = QLabel("")
        self.detect_result.setProperty("role", "hint")
        detect_row.addWidget(self.detect_result)
        detect_row.addStretch(1)
        form.addLayout(detect_row)

        # -- this world -------------------------------------------------------------
        self.world_section = self._section("THIS WORLD")
        form.addWidget(self.world_section)
        self.world_field = widgets.WorldField(
            "World to sync",
            hint="The save filename, without extension — must match on every PC.")
        form.addWidget(self.world_field)
        self.shared_field = widgets.FormField(
            "Shared folder", browse="dir",
            hint="Everyone in the group must point at the same cloud-synced folder.")
        form.addWidget(self.shared_field)
        self.webhook_field = widgets.FormField(
            "Webhook for save notifications (optional)",
            hint="Discord, Slack, or ntfy.sh webhook URL — a short message is "
                 "posted whenever someone shares a save.",
            placeholder="https://discord.com/api/webhooks/…")
        form.addWidget(self.webhook_field)

        accent_col = QVBoxLayout()
        accent_col.setSpacing(6)
        accent_label = QLabel("Banner color")
        accent_label.setProperty("role", "fieldLabel")
        accent_col.addWidget(accent_label)
        self.accent_combo = QComboBox()
        self.accent_combo.setFixedHeight(38)
        self.accent_combo.addItem("Auto (from the world's name)")
        for c in theme.AVATAR_COLORS:
            self.accent_combo.addItem(self._swatch(c), "")
        accent_col.addWidget(self.accent_combo)
        self.accent_row = QWidget()
        self.accent_row.setLayout(accent_col)
        form.addWidget(self.accent_row)

        test_row = QHBoxLayout()
        test_btn = widgets.make_button("Test my setup", "ghost", "check-circle", height=34)
        test_btn.clicked.connect(self.preflight_requested.emit)
        test_row.addWidget(test_btn)
        test_row.addStretch(1)
        form.addLayout(test_row)

        # -- app behavior --------------------------------------------------------------
        form.addWidget(self._section("APP"))
        self.tray_check = QCheckBox("Keep running in the tray when the window closes")
        form.addWidget(self.tray_check)
        self.startup_check = QCheckBox("Start with Windows (quietly, in the tray)")
        if not autostart.available():
            self.startup_check.setVisible(False)
        form.addWidget(self.startup_check)
        self.statuspage_check = QCheckBox(
            "Publish a phone-checkable status page to the shared folder")
        self.statuspage_check.setToolTip(
            "Writes status.html into the shared folder so anyone can check "
            "who's playing from their phone's cloud-drive app.")
        form.addWidget(self.statuspage_check)
        self.chime_check = QCheckBox("A soft chime when the wilds open")
        form.addWidget(self.chime_check)

        self.discord_field = widgets.FormField(
            "Discord application ID (optional)",
            hint="Enables “In the wilds of…” Discord Rich Presence. Create a "
                 "free application at discord.com/developers and paste its ID.",
            placeholder="e.g. 1123456789012345678")
        form.addWidget(self.discord_field)

        # -- host tools --------------------------------------------------------------------
        form.addWidget(self._section("SHARE AN UPDATE"))
        pub_hint = QLabel("Built a new version? Publish it to this world's shared "
                          "folder and everyone is offered the update automatically.")
        pub_hint.setWordWrap(True)
        pub_hint.setProperty("role", "hint")
        form.addWidget(pub_hint)
        pub_row = QHBoxLayout()
        pub_btn = widgets.make_button("Publish this version to friends", "ghost",
                                      "rocket", height=34)
        pub_btn.clicked.connect(self.publish_update_requested.emit)
        pub_row.addWidget(pub_btn)
        pub_row.addStretch(1)
        form.addLayout(pub_row)

        # -- footer ------------------------------------------------------------------------
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet(f"background: {theme.BORDER_SOFT};")
        form.addSpacing(4)
        form.addWidget(divider)

        links = QHBoxLayout()
        logs_btn = widgets.make_button("Open log folder", "subtle", "external", height=32)
        logs_btn.clicked.connect(self._open_logs)
        about_btn = widgets.make_button("About", "subtle", "info", height=32)
        about_btn.clicked.connect(self.about_requested.emit)
        self.forget_btn = widgets.make_button("Forget this world", "subtle", height=32)
        self.forget_btn.setStyleSheet(f"color: {theme.RED_HOVER};")
        self.forget_btn.clicked.connect(self._forget)
        links.addWidget(logs_btn)
        links.addWidget(about_btn)
        links.addStretch(1)
        links.addWidget(self.forget_btn)
        form.addLayout(links)

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

    # -- helpers ---------------------------------------------------------------------
    def _section(self, text):
        label = QLabel(text)
        label.setObjectName("SettingsSection")
        return label

    def _swatch(self, color_hex):
        from PySide6.QtGui import QColor, QIcon, QPixmap
        pm = QPixmap(40, 18)
        pm.fill(QColor(color_hex))
        return QIcon(pm)

    def load(self, cfg: dict, world: dict | None):
        cfg = cfg or {}
        self.name_field.edit.setText(cfg.get("player_name", ""))
        emoji = cfg.get("player_emoji", "")
        self.emoji_combo.setCurrentIndex(
            EMOJI_CHOICES.index(emoji) if emoji in EMOJI_CHOICES else 0)
        color = cfg.get("player_color", "")
        self.color_combo.setCurrentIndex(
            theme.AVATAR_COLORS.index(color) + 1 if color in theme.AVATAR_COLORS else 0)
        self.save_dir_field.edit.setText(cfg.get("local_save_dir", str(paths.DEFAULT_SAVE_DIR)))
        self.exe_field.edit.setText(cfg.get("exe_path") or "")
        self.detect_result.setText("")
        self.tray_check.setChecked(bool(cfg.get("close_to_tray", True)))
        self.startup_check.setChecked(autostart.is_enabled())
        self.statuspage_check.setChecked(bool(cfg.get("publish_status_page", True)))
        self.chime_check.setChecked(bool(cfg.get("play_chime", True)))
        self.discord_field.edit.setText(cfg.get("discord_app_id") or "")

        self._world_id = world["id"] if world else None
        has_world = world is not None
        for w in (self.world_section, self.world_field, self.shared_field,
                  self.webhook_field, self.forget_btn, self.accent_row):
            w.setVisible(has_world)
        if world:
            self.world_field.refresh(self.save_dir_field.value(), keep_current=False)
            self.world_field.combo.setCurrentText(world.get("world_name", ""))
            self.shared_field.edit.setText(world.get("sync_dir", ""))
            self.webhook_field.edit.setText(world.get("webhook_url") or "")
            accent = world.get("accent") or ""
            self.accent_combo.setCurrentIndex(
                theme.AVATAR_COLORS.index(accent) + 1
                if accent in theme.AVATAR_COLORS else 0)

        for f in (self.name_field, self.save_dir_field, self.shared_field,
                  self.exe_field, self.webhook_field):
            f.clear_error()
        self.world_field.clear_error()

    def _rescan(self):
        self.world_field.refresh(self.save_dir_field.value())

    def _detect_exe(self):
        found = steam.find_game_exe()
        if found:
            self.exe_field.edit.setText(str(found))
            self.detect_result.setText("Found it.")
        else:
            self.detect_result.setText("Couldn't find it — Steam launch works regardless.")

    def _open_logs(self):
        paths.LOG_DIR.mkdir(parents=True, exist_ok=True)
        os.startfile(str(paths.LOG_DIR))  # noqa: S606

    def _forget(self):
        if self._world_id:
            self.remove_world_requested.emit(self._world_id)

    def _submit(self):
        ok = True
        if not self.name_field.value():
            self.name_field.set_error("A name is required.")
            ok = False
        if not self.save_dir_field.value():
            self.save_dir_field.set_error("The game's save folder is required.")
            ok = False
        if self._world_id:
            if not self.world_field.value():
                self.world_field.set_error("A world name is required.")
                ok = False
            if not self.shared_field.value():
                self.shared_field.set_error("The shared folder is required.")
                ok = False
        webhook_url = self.webhook_field.value()
        if webhook_url and not webhook_url.startswith(("http://", "https://")):
            self.webhook_field.set_error("A webhook is a URL — it should start with https://")
            ok = False
        exe = self.exe_field.value()
        if exe and not os.path.isfile(exe):
            self.exe_field.set_error("That file doesn't exist — leave empty to use Steam.")
            ok = False
        if not ok:
            return

        emoji = EMOJI_CHOICES[self.emoji_combo.currentIndex()]
        color_i = self.color_combo.currentIndex()
        color = theme.AVATAR_COLORS[color_i - 1] if color_i > 0 else ""
        global_fields = {
            "player_name": self.name_field.value(),
            "player_emoji": emoji,
            "player_color": color,
            "local_save_dir": self.save_dir_field.value(),
            "exe_path": exe or None,
            "close_to_tray": self.tray_check.isChecked(),
            "launch_on_startup": self.startup_check.isChecked(),
            "publish_status_page": self.statuspage_check.isChecked(),
            "play_chime": self.chime_check.isChecked(),
            "discord_app_id": self.discord_field.value(),
        }
        world_fields = {}
        if self._world_id:
            accent_i = self.accent_combo.currentIndex()
            world_fields = {
                "id": self._world_id,
                "world_name": self.world_field.value(),
                "sync_dir": self.shared_field.value(),
                "webhook_url": webhook_url or None,
                "accent": theme.AVATAR_COLORS[accent_i - 1] if accent_i > 0 else None,
            }
        if autostart.available():
            autostart.set_enabled(self.startup_check.isChecked())
        self.saved.emit(global_fields, world_fields)
