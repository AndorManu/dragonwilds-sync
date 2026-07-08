"""Onboarding: welcome → name → create-or-join fork → done in under a minute.

Also reused as the "Add a world" flow for already-configured users (the name
step is skipped and Back from the fork returns to the main screen).

`finished` emits a payload:
  {"kind": "create"|"join", "player_name", "local_save_dir",
   "world_name", "sync_dir", "share_link"}
"""

import getpass
import os
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..core import clouds, invite, paths
from . import icons, theme, widgets

STEP_WELCOME, STEP_NAME, STEP_CHOICE = 0, 1, 2
STEP_CREATE_WORLD, STEP_CREATE_SHARED = 3, 4
STEP_JOIN_CODE, STEP_JOIN_WATCH = 5, 6

WATCH_INTERVAL_MS = 2500


class StepDots(QWidget):
    def __init__(self, count=4, parent=None):
        super().__init__(parent)
        self._dots = []
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(7)
        row.addStretch(1)
        for _ in range(count):
            d = QLabel()
            d.setFixedSize(7, 7)
            self._dots.append(d)
            row.addWidget(d)
        row.addStretch(1)
        self.set_active(0)

    def set_active(self, index):
        for i, d in enumerate(self._dots):
            color = theme.ACCENT if i <= index else theme.BORDER
            d.setStyleSheet(f"background: {color}; border-radius: 3px;")


class OnboardingPage(QWidget):
    finished = Signal(dict)
    cancelled = Signal()      # only from "Add a world" mode

    def __init__(self, parent=None):
        super().__init__(parent)
        self.add_mode = False
        self._existing_name = ""
        self._join_info = None
        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(WATCH_INTERVAL_MS)
        self._watch_timer.timeout.connect(self._watch_tick)

        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 4, 36, 28)
        root.addWidget(self._stack)

        self._stack.addWidget(self._welcome_step())      # 0
        self._stack.addWidget(self._name_step())         # 1
        self._stack.addWidget(self._choice_step())       # 2
        self._stack.addWidget(self._world_step())        # 3
        self._stack.addWidget(self._shared_step())       # 4
        self._stack.addWidget(self._join_code_step())    # 5
        self._stack.addWidget(self._join_watch_step())   # 6

    # -- modes ------------------------------------------------------------------
    def start_fresh(self):
        self.add_mode = False
        self._watch_timer.stop()
        self._go(STEP_WELCOME)

    def start_add_world(self, player_name: str):
        """Skip straight to the fork; Back there cancels to the main screen."""
        self.add_mode = True
        self._existing_name = player_name
        self._watch_timer.stop()
        self._go(STEP_CHOICE)

    # -- shared scaffolding ---------------------------------------------------------
    def _step_scaffold(self, dot_index, title, subtitle, back_to=None):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)

        header = QHBoxLayout()
        if back_to is not None:
            back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
            back.clicked.connect(back_to)
            header.addWidget(back)
        header.addStretch(1)
        box.addLayout(header)
        box.addSpacing(14)

        dots = StepDots(4)
        dots.set_active(dot_index)
        box.addWidget(dots)
        box.addSpacing(24)

        t = QLabel(title)
        t.setStyleSheet("font-size: 21px; font-weight: 650;")
        t.setWordWrap(True)
        box.addWidget(t)
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 13px;")
        box.addSpacing(6)
        box.addWidget(s)
        box.addSpacing(20)

        content = QVBoxLayout()
        content.setSpacing(14)
        box.addLayout(content)
        box.addStretch(1)
        return page, box, content

    def _continue_row(self, box, label, slot):
        row = QHBoxLayout()
        row.addStretch(1)
        btn = widgets.make_button(label, "primary", height=44)
        btn.setMinimumWidth(150)
        btn.clicked.connect(slot)
        row.addWidget(btn)
        box.addSpacing(8)
        box.addLayout(row)
        return btn

    def _go(self, index):
        if index != STEP_JOIN_WATCH:
            self._watch_timer.stop()
        self._stack.setCurrentIndex(index)

    def _player_name(self) -> str:
        return self._existing_name if self.add_mode else self.name_field.value()

    # -- step 0: welcome -----------------------------------------------------------
    def _welcome_step(self):
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.addStretch(5)

        mark = QLabel()
        mark.setPixmap(icons.mark_pixmap(60))
        mark.setAlignment(Qt.AlignHCenter)
        box.addWidget(mark)
        box.addSpacing(18)

        title = QLabel("Dragonwilds Sync")
        title.setAlignment(Qt.AlignHCenter)
        title.setStyleSheet(
            f"font-family: '{theme.deco_family()}'; font-size: 32px; font-weight: 700;"
            f"color: {theme.GOLD_TEXT}; letter-spacing: 1px;")
        box.addWidget(title)

        tag = QLabel("One world, shared between friends.")
        tag.setAlignment(Qt.AlignHCenter)
        tag.setStyleSheet(
            f"font-family: '{theme.display_family()}'; color: {theme.ACCENT};"
            f"font-size: 13px; font-weight: 600; letter-spacing: 1px;")
        box.addSpacing(6)
        box.addWidget(tag)

        body = QLabel("Take turns in the same Dragonwilds world without renting a server. "
                      "Whoever plays next always picks up the newest save — automatically.")
        body.setAlignment(Qt.AlignHCenter)
        body.setWordWrap(True)
        body.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        box.addSpacing(14)
        box.addWidget(body)
        box.addSpacing(30)

        btn = widgets.make_button("Set me up", "primary", height=46)
        btn.setMinimumWidth(180)
        btn.clicked.connect(lambda: self._go(STEP_NAME))
        box.addWidget(btn, 0, Qt.AlignHCenter)

        cap = QLabel("Takes under a minute  ·  No account needed")
        cap.setAlignment(Qt.AlignHCenter)
        cap.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;")
        box.addSpacing(12)
        box.addWidget(cap)
        box.addStretch(6)
        return page

    # -- step 1: name ---------------------------------------------------------------
    def _name_step(self):
        page, box, content = self._step_scaffold(
            0, "What should friends call you?",
            "Your name shows up next to every save you share.",
            back_to=lambda: self._go(STEP_WELCOME))
        suggestion = getpass.getuser().capitalize() if getpass.getuser() else ""
        self.name_field = widgets.FormField("Your name", suggestion,
                                            placeholder="e.g. Andor")
        content.addWidget(self.name_field)
        self._continue_row(box, "Continue", self._submit_name)
        self.name_field.edit.returnPressed.connect(self._submit_name)
        return page

    def _submit_name(self):
        if not self.name_field.value():
            self.name_field.set_error("Everyone needs a name — even a dragon.")
            return
        self.name_field.clear_error()
        self._go(STEP_CHOICE)

    # -- step 2: create or join --------------------------------------------------------
    def _choice_step(self):
        page, box, content = self._step_scaffold(
            1, "How are you starting out?",
            "Create a world for your group, or join one a friend already shares.",
            back_to=self._back_from_choice)

        create = widgets.OptionCard(
            "sparkle", "Create a new world",
            "You have (or will make) the world save — set up the shared folder "
            "and invite the others.")
        create.set_on_click(lambda: self._go(STEP_CREATE_WORLD))
        content.addWidget(create)

        join = widgets.OptionCard(
            "link", "Join with an invite code",
            "A friend sent you a code from their app — paste it and you're in.")
        join.set_on_click(lambda: self._go(STEP_JOIN_CODE))
        content.addWidget(join)
        return page

    def _back_from_choice(self):
        if self.add_mode:
            self.cancelled.emit()
        else:
            self._go(STEP_NAME)

    # -- step 3: create - world --------------------------------------------------------
    def _world_step(self):
        page, box, content = self._step_scaffold(
            2, "Where does your world live?",
            "This is the game's save folder on this PC. We've already found "
            "the usual spot — just pick the world you all share.",
            back_to=lambda: self._go(STEP_CHOICE))
        self.save_dir_field = widgets.FormField(
            "Dragonwilds save folder", str(paths.DEFAULT_SAVE_DIR), browse="dir")
        self.save_dir_field.edit.editingFinished.connect(self._rescan_worlds)
        content.addWidget(self.save_dir_field)

        self.world_field = widgets.WorldField("World to sync", hint="")
        content.addWidget(self.world_field)
        self._rescan_worlds()
        self._continue_row(box, "Continue", self._submit_world)
        return page

    def _rescan_worlds(self):
        names = self.world_field.refresh(self.save_dir_field.value())
        if names:
            self.world_field.note.setText(
                f"Found {len(names)} world{'s' if len(names) != 1 else ''} in this folder.")
            self.world_field.note.setProperty("role", "hint")
            self.world_field.note.setVisible(True)
        else:
            self.world_field.note.setText(
                "No saves found here yet — fine if the world lives on a friend's PC. "
                "Type its name exactly as they see it.")
            self.world_field.note.setVisible(True)

    def _submit_world(self):
        ok = True
        if not self.save_dir_field.value():
            self.save_dir_field.set_error("Point me at the game's save folder.")
            ok = False
        if not self.world_field.value():
            self.world_field.set_error("Which world are you sharing?")
            ok = False
        if ok:
            self.world_field.clear_error()
            self._go(STEP_CREATE_SHARED)

    # -- step 4: create - shared folder ---------------------------------------------------
    def _shared_step(self):
        page, box, content = self._step_scaffold(
            3, "Pick the shared folder",
            "A folder inside a cloud drive that every friend syncs to their "
            "own PC — Google Drive, Dropbox, OneDrive… Everyone must point "
            "at the same one.",
            back_to=lambda: self._go(STEP_CREATE_WORLD))

        cloud_roots = clouds.detect_cloud_roots()
        if cloud_roots:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(8)
            lab = QLabel("On this PC:")
            lab.setProperty("role", "hint")
            chip_row.addWidget(lab)
            seen = set()
            for label, root in cloud_roots:
                if label in seen:
                    continue
                seen.add(label)
                chip = QPushButton(label)
                chip.setProperty("variant", "chip")
                chip.setCursor(Qt.PointingHandCursor)
                suggested = root / "Dragonwilds Sync"
                chip.setToolTip(str(suggested))
                chip.clicked.connect(
                    lambda _=False, s=suggested: self.shared_field.edit.setText(str(s)))
                chip_row.addWidget(chip)
            chip_row.addStretch(1)
            content.addLayout(chip_row)
        else:
            warn = QLabel("No cloud drive found on this PC — you'll need one "
                          "(free) to link everyone's saves together.")
            warn.setWordWrap(True)
            warn.setStyleSheet(f"color: {theme.AMBER}; font-size: 12.5px;")
            content.addWidget(warn)
            dl = widgets.make_button("Download Google Drive", "ghost",
                                     "download-cloud", height=38)
            dl.clicked.connect(lambda: webbrowser.open(clouds.GOOGLE_DRIVE_DOWNLOAD_URL))
            content.addWidget(dl)

        self.shared_field = widgets.FormField(
            "Shared folder", "", browse="dir",
            hint="We'll create it if it doesn't exist yet.",
            placeholder=r"e.g. C:\Users\you\OneDrive\Dragonwilds Sync")
        content.addWidget(self.shared_field)
        self._continue_row(box, "Enter the wilds", self._submit_create)
        return page

    def _submit_create(self):
        shared = self.shared_field.value()
        if not shared:
            self.shared_field.set_error("This is the folder that links you all together.")
            return
        try:
            Path(shared).mkdir(parents=True, exist_ok=True)
        except OSError:
            self.shared_field.set_error("Couldn't create that folder — check the path.")
            return
        self.shared_field.clear_error()
        self.finished.emit({
            "kind": "create",
            "player_name": self._player_name(),
            "local_save_dir": self.save_dir_field.value(),
            "world_name": self.world_field.value(),
            "sync_dir": shared,
            "share_link": None,
        })

    # -- step 5: join - paste code ----------------------------------------------------------
    def _join_code_step(self):
        page, box, content = self._step_scaffold(
            2, "Paste your invite code",
            "Your friend generates it in their app under “Invite friends” and "
            "sends it any way they like.",
            back_to=lambda: self._go(STEP_CHOICE))
        self.code_field = widgets.FormField(
            "Invite code", "", placeholder="DWS1.…")
        content.addWidget(self.code_field)
        self._continue_row(box, "Continue", self._submit_code)
        self.code_field.edit.returnPressed.connect(self._submit_code)
        return page

    def _submit_code(self):
        try:
            self._join_info = invite.decode(self.code_field.value())
        except invite.InviteError as e:
            self.code_field.set_error(str(e))
            return
        self.code_field.clear_error()
        self._start_watching()
        self._go(STEP_JOIN_WATCH)

    # -- step 6: join - watch for the folder ---------------------------------------------------
    def _join_watch_step(self):
        page, box, content = self._step_scaffold(
            3, "Add the folder to your Drive",
            "One click on your friend's share link, then this screen finishes "
            "itself — no digging through folders.",
            back_to=lambda: self._go(STEP_JOIN_CODE))

        self.join_summary = QLabel("")
        self.join_summary.setWordWrap(True)
        self.join_summary.setStyleSheet(
            f"background: {theme.SURFACE}; border: 1px solid {theme.BORDER_SOFT};"
            f"border-radius: 10px; padding: 12px; font-size: 12.5px;")
        content.addWidget(self.join_summary)

        self.open_link_btn = widgets.make_button(
            "Open the invite link", "primary", height=42)
        self.open_link_btn.clicked.connect(self._open_share_link)
        content.addWidget(self.open_link_btn)

        hint = QLabel("In the browser: sign in to Google, then choose "
                      "“Add shortcut to Drive” (or “Add to My Drive”). "
                      "Google Drive will start syncing the folder to this PC.")
        hint.setWordWrap(True)
        hint.setProperty("role", "hint")
        content.addWidget(hint)

        watch_row = QHBoxLayout()
        watch_row.setSpacing(10)
        self.watch_spinner = widgets.Spinner(18)
        watch_row.addWidget(self.watch_spinner)
        self.watch_label = QLabel("Watching for the folder to appear…")
        self.watch_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        self.watch_label.setWordWrap(True)
        watch_row.addWidget(self.watch_label, 1)
        content.addSpacing(6)
        content.addLayout(watch_row)

        # Cloud-drive missing panel (swapped in when nothing is detected).
        self.no_cloud_panel = QWidget()
        nc = QVBoxLayout(self.no_cloud_panel)
        nc.setContentsMargins(0, 6, 0, 0)
        nc.setSpacing(8)
        nc_label = QLabel("Google Drive doesn't seem to be set up on this PC — "
                          "the folder can't sync here without it.")
        nc_label.setWordWrap(True)
        nc_label.setStyleSheet(f"color: {theme.AMBER}; font-size: 12.5px;")
        nc.addWidget(nc_label)
        dl_btn = widgets.make_button("Download Google Drive", "ghost",
                                     "download-cloud", height=38)
        dl_btn.clicked.connect(lambda: webbrowser.open(clouds.GOOGLE_DRIVE_DOWNLOAD_URL))
        nc.addWidget(dl_btn)
        nc_alt = QLabel("Using Dropbox or OneDrive instead? Their shared folders "
                        "work too — browse to it below once it syncs.")
        nc_alt.setWordWrap(True)
        nc_alt.setProperty("role", "hint")
        nc.addWidget(nc_alt)
        content.addWidget(self.no_cloud_panel)

        browse_row = QHBoxLayout()
        browse_row.addStretch(1)
        browse_btn = widgets.make_button("Browse for it manually", "subtle", height=30)
        browse_btn.clicked.connect(self._browse_manually)
        browse_row.addWidget(browse_btn)
        box.addLayout(browse_row)
        return page

    def _start_watching(self):
        info = self._join_info
        link_note = "" if info.get("share_link") else (
            "\nThis code has no link in it — ask your friend to share the "
            "folder with you in their cloud drive.")
        self.join_summary.setText(
            f"World:  {info['world_name']}\nFolder:  {info['folder_name']}{link_note}")
        self.open_link_btn.setVisible(bool(info.get("share_link")))
        self.no_cloud_panel.setVisible(not clouds.any_cloud_present())
        self.watch_label.setText("Watching for the folder to appear…")
        self._watch_timer.start()
        self._watch_tick()

    def _open_share_link(self):
        if self._join_info and self._join_info.get("share_link"):
            webbrowser.open(self._join_info["share_link"])
            self.watch_label.setText(
                "Browser opened. Once you add the folder to your Drive, "
                "I'll spot it here automatically — usually within a minute.")

    def _watch_tick(self):
        info = self._join_info
        if not info:
            return
        found = clouds.find_synced_folder(info["folder_name"], info["world_name"])
        if found:
            self._watch_timer.stop()
            self._finish_join(found)

    def _browse_manually(self):
        from PySide6.QtWidgets import QFileDialog
        start = str(Path.home())
        roots = clouds.detect_cloud_roots()
        if roots:
            start = str(roots[0][1])
        chosen = QFileDialog.getExistingDirectory(self, "Find the shared folder", start)
        if chosen:
            self._watch_timer.stop()
            self._finish_join(Path(chosen))

    def _finish_join(self, folder: Path):
        info = self._join_info
        self.finished.emit({
            "kind": "join",
            "player_name": self._player_name(),
            "local_save_dir": str(paths.DEFAULT_SAVE_DIR),
            "world_name": info["world_name"],
            "sync_dir": str(folder),
            "share_link": info.get("share_link"),
        })
