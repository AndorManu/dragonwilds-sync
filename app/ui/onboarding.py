"""First-run onboarding: welcome → name → world → shared folder. Under a minute."""

import getpass
import os
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPushButton, QStackedWidget,
                               QVBoxLayout, QWidget)

from ..core import paths
from . import icons, theme, widgets


def detect_cloud_roots() -> list[tuple[str, Path]]:
    """Cloud-synced folders already on this machine, for one-click suggestions."""
    roots: list[tuple[str, Path]] = []
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive and Path(onedrive).exists():
        roots.append(("OneDrive", Path(onedrive)))
    dropbox = Path.home() / "Dropbox"
    if dropbox.exists():
        roots.append(("Dropbox", dropbox))
    for candidate in (Path.home() / "Google Drive", Path("G:/My Drive")):
        if candidate.exists():
            roots.append(("Google Drive", candidate))
            break
    return roots


class StepDots(QWidget):
    def __init__(self, count=3, parent=None):
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

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stack = QStackedWidget()
        root = QVBoxLayout(self)
        root.setContentsMargins(36, 4, 36, 28)
        root.addWidget(self._stack)

        self._stack.addWidget(self._welcome_step())
        self._stack.addWidget(self._name_step())
        self._stack.addWidget(self._world_step())
        self._stack.addWidget(self._shared_step())

    # -- shared scaffolding --------------------------------------------------
    def _step_scaffold(self, step_index, title, subtitle):
        """Returns (page_widget, content_layout). Steps 1-3 get dots + back."""
        page = QWidget()
        box = QVBoxLayout(page)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)

        header = QHBoxLayout()
        if step_index > 0:
            back = widgets.icon_button("chevron-left", theme.TEXT_DIM,
                                       tooltip="Back")
            back.clicked.connect(lambda: self._go(step_index - 1))
            header.addWidget(back)
        header.addStretch(1)
        box.addLayout(header)
        box.addSpacing(18)

        if step_index > 0:
            dots = StepDots(3)
            dots.set_active(step_index - 1)
            box.addWidget(dots)
            box.addSpacing(26)

        t = QLabel(title)
        t.setStyleSheet("font-size: 21px; font-weight: 650;")
        t.setWordWrap(True)
        box.addWidget(t)
        s = QLabel(subtitle)
        s.setWordWrap(True)
        s.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 13px;")
        box.addSpacing(6)
        box.addWidget(s)
        box.addSpacing(22)

        content = QVBoxLayout()
        content.setSpacing(16)
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
        self._stack.setCurrentIndex(index)

    # -- step 0: welcome -------------------------------------------------------
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
        title.setStyleSheet("font-size: 26px; font-weight: 700;")
        box.addWidget(title)

        tag = QLabel("One world, shared between friends.")
        tag.setAlignment(Qt.AlignHCenter)
        tag.setStyleSheet(f"color: {theme.ACCENT}; font-size: 13.5px; font-weight: 600;")
        box.addSpacing(4)
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
        btn.clicked.connect(lambda: self._go(1))
        box.addWidget(btn, 0, Qt.AlignHCenter)

        cap = QLabel("Takes under a minute  ·  No account needed")
        cap.setAlignment(Qt.AlignHCenter)
        cap.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;")
        box.addSpacing(12)
        box.addWidget(cap)
        box.addStretch(6)
        return page

    # -- step 1: name ---------------------------------------------------------
    def _name_step(self):
        page, box, content = self._step_scaffold(
            1, "What should friends call you?",
            "Your name shows up next to every save you share.")
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
        self._go(2)

    # -- step 2: world ----------------------------------------------------------
    def _world_step(self):
        page, box, content = self._step_scaffold(
            2, "Where does your world live?",
            "This is the game's save folder on this PC. We've already found "
            "the usual spot — just pick the world you all share.")
        self.save_dir_field = widgets.FormField(
            "Dragonwilds save folder", str(paths.DEFAULT_SAVE_DIR), browse="dir")
        self.save_dir_field.edit.editingFinished.connect(self._rescan_worlds)
        content.addWidget(self.save_dir_field)

        self.world_field = widgets.WorldField(
            "World to sync", hint="")
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
            self._go(3)

    # -- step 3: shared folder ---------------------------------------------------
    def _shared_step(self):
        page, box, content = self._step_scaffold(
            3, "Pick the shared folder",
            "A folder inside a cloud drive that every friend syncs to their "
            "own PC — Google Drive, Dropbox, OneDrive… Everyone must point "
            "at the same one.")

        clouds = detect_cloud_roots()
        if clouds:
            chip_row = QHBoxLayout()
            chip_row.setSpacing(8)
            lab = QLabel("On this PC:")
            lab.setProperty("role", "hint")
            chip_row.addWidget(lab)
            for label, root in clouds:
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

        self.shared_field = widgets.FormField(
            "Shared folder", "", browse="dir",
            hint="We'll create it if it doesn't exist yet.",
            placeholder=r"e.g. C:\Users\you\OneDrive\Dragonwilds Sync")
        content.addWidget(self.shared_field)
        self._continue_row(box, "Enter the wilds", self._submit_all)
        return page

    def _submit_all(self):
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
            "player_name": self.name_field.value(),
            "local_save_dir": self.save_dir_field.value(),
            "world_name": self.world_field.value(),
            "sync_dir": shared,
            "exe_path": None,
            "steam_app_id": paths.STEAM_APP_ID,
        })
