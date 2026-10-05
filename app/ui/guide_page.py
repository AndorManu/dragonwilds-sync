"""Setup guide: how to get one game ready for WorldSync, step by step.

Opened from the game's setup flow and from the world menu. It shows what to
do in the game first, where the saves live (and whether they were found on
this PC), and the few rules that hold for every game.
"""

import os

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QScrollArea, QVBoxLayout,
                               QWidget)

from ..core import games
from . import theme, widgets
from .banner import WorldBanner


def _step_row(number: int, text: str) -> QWidget:
    row = QWidget()
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.setSpacing(12)
    badge = QLabel(str(number))
    badge.setFixedSize(24, 24)
    badge.setAlignment(Qt.AlignCenter)
    badge.setStyleSheet(
        f"background: {theme.ACCENT}; color: {theme.ON_ACCENT}; border-radius: 12px;"
        "font-size: 12px; font-weight: 700;")
    box.addWidget(badge, 0, Qt.AlignTop)
    label = QLabel(text)
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme.TEXT}; font-size: 12.5px;")
    box.addWidget(label, 1)
    return row


def _bullet_row(text: str) -> QLabel:
    label = QLabel(f"·  {text}")
    label.setWordWrap(True)
    label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
    return label


class GuidePage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._found = None
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        hero = QWidget()
        hero.setFixedHeight(112)
        self.banner = WorldBanner(112, hero)
        overlay = QWidget(hero)
        overlay.setStyleSheet("background: transparent;")
        ov = QVBoxLayout(overlay)
        ov.setContentsMargins(14, 8, 18, 12)
        top = QHBoxLayout()
        back = widgets.icon_button("chevron-left", "#FFFFFF", tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        top.addWidget(back)
        top.addStretch(1)
        ov.addLayout(top)
        ov.addStretch(1)
        self.title = QLabel("")
        ov.addWidget(self.title)
        hero.resizeEvent = lambda e: (self.banner.setGeometry(0, 0, hero.width(), 112),
                                      overlay.setGeometry(0, 0, hero.width(), 112))
        root.addWidget(hero)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.box = QVBoxLayout(self.body)
        self.box.setContentsMargins(24, 14, 22, 20)
        self.box.setSpacing(10)
        scroll.setWidget(self.body)
        root.addWidget(scroll, 1)

    # -- public -----------------------------------------------------------------
    def load(self, profile, save_dir: str = ""):
        self.banner.set_scene(theme.scene())
        self.banner.set_world(profile.name)
        self.title.setText(f"Setting up {profile.short}")
        self.title.setStyleSheet(
            "background: transparent; color: #FFFFFF;"
            f"font-family: '{theme.deco_family()}'; font-size: 24px; font-weight: 700;")

        while self.box.count():
            item = self.box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not profile.verified:
            beta = QLabel(f"{profile.name} support is in beta: it follows the save layout the "
                          f"community documents. Every overwrite is backed up first, and "
                          f"reports on GitHub move it to tested.")
            beta.setWordWrap(True)
            beta.setStyleSheet(
                "background: rgba(242,180,65,0.08); border: 1px solid rgba(242,180,65,0.28);"
                f"border-radius: 10px; padding: 10px 12px; color: {theme.TEXT_DIM};"
                "font-size: 11.5px;")
            self.box.addWidget(beta)

        self._section("In the game")
        for i, step in enumerate(games.setup_steps(profile), 1):
            self.box.addWidget(_step_row(i, step))

        self._section("Where the saves live")
        for template in profile.save_roots:
            path = QLabel(games.human_save_path(template))
            path.setWordWrap(True)
            path.setTextInteractionFlags(Qt.TextSelectableByMouse)
            path.setStyleSheet(
                f"background: {theme.FIELD_BG}; border: 1px solid {theme.BORDER};"
                "border-radius: 8px; padding: 8px 10px; font-family: Consolas, monospace;"
                f"font-size: 11.5px; color: {theme.TEXT_DIM};")
            self.box.addWidget(path)
        found = save_dir if save_dir and os.path.isdir(save_dir) else None
        self._found = found
        status_row = QHBoxLayout()
        status = QLabel("Found on this PC." if found else
                        "Not on this PC yet. Start the game once and load a world, "
                        "then WorldSync finds it.")
        status.setWordWrap(True)
        status.setStyleSheet(
            f"color: {theme.ACCENT if found else theme.TEXT_FAINT}; font-size: 12px;")
        status_row.addWidget(status, 1)
        if found:
            open_btn = widgets.make_button("Open folder", "ghost", "folder", height=30)
            open_btn.clicked.connect(lambda: os.startfile(found))  # noqa: S606
            status_row.addWidget(open_btn, 0, Qt.AlignTop)
        holder = QWidget()
        holder.setLayout(status_row)
        self.box.addWidget(holder)

        self._section("For the whole group")
        for line in games.COMMON_STEPS:
            self.box.addWidget(_bullet_row(line))
        self.box.addStretch(1)

    def _section(self, text):
        label = QLabel(theme.caps(text))
        label.setObjectName("SectionLabel")
        self.box.addSpacing(6)
        self.box.addWidget(label)
