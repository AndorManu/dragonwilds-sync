"""Invite friends: three honest steps and a copy-pasteable code.

We can't create the cloud share link for them (that would need a full OAuth
integration) — so the app makes every step around that one click disappear:
open the right places, remember the link, generate the code.
"""

import os
import webbrowser
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QPlainTextEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from ..core import invite
from . import theme, widgets


class InvitePage(QWidget):
    back_requested = Signal()
    share_link_saved = Signal(str, str)      # world_id, link

    def __init__(self, parent=None):
        super().__init__(parent)
        self._world = None

        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        self.title = QLabel("Invite friends")
        self.title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(self.title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        form = QVBoxLayout(body)
        form.setContentsMargins(2, 2, 10, 2)
        form.setSpacing(14)

        intro = QLabel("Friends need two things: the shared folder, and this "
                       "world's name. An invite code carries both — you only "
                       "have to share the folder once.")
        intro.setWordWrap(True)
        intro.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        form.addWidget(intro)

        step1 = QLabel("1  ·  SHARE THE FOLDER (ONCE)")
        step1.setObjectName("SectionLabel")
        form.addWidget(step1)
        s1 = QLabel("In Google Drive: right-click the folder → Share → "
                    "“Anyone with the link” → Copy link. (Dropbox/OneDrive: "
                    "their usual share-folder option.)")
        s1.setWordWrap(True)
        s1.setProperty("role", "hint")
        form.addWidget(s1)
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        open_folder = widgets.make_button("Open folder location", "ghost",
                                          "folder", height=34)
        open_folder.clicked.connect(self._open_folder)
        open_drive = widgets.make_button("Open Google Drive", "ghost",
                                         "external", height=34)
        open_drive.clicked.connect(lambda: webbrowser.open("https://drive.google.com"))
        btn_row.addWidget(open_folder)
        btn_row.addWidget(open_drive)
        btn_row.addStretch(1)
        form.addLayout(btn_row)

        step2 = QLabel("2  ·  PASTE THE SHARE LINK")
        step2.setObjectName("SectionLabel")
        form.addWidget(step2)
        self.link_field = widgets.FormField(
            "Share link", "",
            hint="Remembered for this world — next invites are one click.",
            placeholder="https://drive.google.com/…")
        form.addWidget(self.link_field)

        step3 = QLabel("3  ·  SEND THE CODE")
        step3.setObjectName("SectionLabel")
        form.addWidget(step3)
        gen = widgets.make_button("Generate invite code", "primary", height=40)
        gen.clicked.connect(self._generate)
        form.addWidget(gen)

        self.code_box = QPlainTextEdit()
        self.code_box.setReadOnly(True)
        self.code_box.setFixedHeight(84)
        self.code_box.setVisible(False)
        form.addWidget(self.code_box)

        self.copy_btn = widgets.make_button("Copy code", "ghost", "copy", height=36)
        self.copy_btn.clicked.connect(self._copy)
        self.copy_btn.setVisible(False)
        form.addWidget(self.copy_btn)

        self.outro = QLabel("Send it over chat. Your friend picks “Join with an "
                            "invite code” in their app — everything else is automatic.")
        self.outro.setWordWrap(True)
        self.outro.setProperty("role", "hint")
        self.outro.setVisible(False)
        form.addWidget(self.outro)
        form.addStretch(1)

        scroll.setWidget(body)
        root.addWidget(scroll, 1)

    def load(self, world: dict):
        self._world = world
        self.title.setText(f"Invite friends — {world['world_name']}")
        self.link_field.edit.setText(world.get("share_link") or "")
        self.link_field.clear_error()
        self.code_box.setVisible(False)
        self.copy_btn.setVisible(False)
        self.outro.setVisible(False)

    def _open_folder(self):
        if self._world and Path(self._world["sync_dir"]).exists():
            os.startfile(self._world["sync_dir"])  # noqa: S606

    def _generate(self):
        link = self.link_field.value()
        if link and not (link.startswith("http://") or link.startswith("https://")):
            self.link_field.set_error("That doesn't look like a link — it should start with https://")
            return
        self.link_field.clear_error()
        if link != (self._world.get("share_link") or ""):
            self.share_link_saved.emit(self._world["id"], link)
            self._world["share_link"] = link
        folder_name = Path(self._world["sync_dir"]).name
        code = invite.encode(self._world["world_name"], folder_name, link or None)
        self.code_box.setPlainText(code)
        self.code_box.setVisible(True)
        self.copy_btn.setVisible(True)
        self.outro.setVisible(True)
        if not link:
            self.link_field.set_error(
                "No link — the code still works, but you'll have to share the "
                "folder with each friend yourself.")

    def _copy(self):
        QGuiApplication.clipboard().setText(self.code_box.toPlainText())
        self.copy_btn.setText("Copied!")
        from PySide6.QtCore import QTimer
        QTimer.singleShot(1600, lambda: self.copy_btn.setText("Copy code"))
