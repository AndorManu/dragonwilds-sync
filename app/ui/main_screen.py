"""The home screen: status hero, the Play button, and the session feed."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QScrollArea,
                               QSizePolicy, QStackedWidget, QVBoxLayout, QWidget)

from .. import __version__
from . import format as fmt
from . import icons, theme, widgets

FEED_TITLE = "RECENT SESSIONS"


class HeroIcon(QFrame):
    """56px circle that hosts either a static icon, a spinner, or the pulse."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self._stack = QStackedWidget(self)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self._stack)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        self._spinner_wrap = self._center(widgets.Spinner(26))
        self._dot_wrap = self._center(widgets.PulsingDot(18))
        self._stack.addWidget(self._icon_label)
        self._stack.addWidget(self._spinner_wrap)
        self._stack.addWidget(self._dot_wrap)

    def _center(self, w):
        wrap = QWidget()
        wrap.setStyleSheet("background: transparent; border: none;")
        lay = QVBoxLayout(wrap)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(w, 0, Qt.AlignCenter)
        return wrap

    def _tint(self, color_hex):
        c = color_hex.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        self.setStyleSheet(
            f"HeroIcon {{ background: rgba({r},{g},{b},0.13);"
            f"border: 1px solid rgba({r},{g},{b},0.25); border-radius: 28px; }}")

    def show_icon(self, name, color):
        self._icon_label.setPixmap(icons.pixmap(name, color, 26))
        self._tint(color)
        self._stack.setCurrentWidget(self._icon_label)

    def show_spinner(self):
        self._tint(theme.ACCENT)
        self._stack.setCurrentWidget(self._spinner_wrap)

    def show_pulse(self):
        self._tint(theme.ACCENT)
        self._stack.setCurrentWidget(self._dot_wrap)


class MainPage(QWidget):
    play_clicked = Signal()
    save_clicked = Signal()
    refresh_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._snapshot = None
        self._phase = "idle"
        self._me = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 8, 24, 16)
        root.setSpacing(14)

        # -- hero card ------------------------------------------------------
        hero = QFrame()
        hero.setObjectName("Card")
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(20, 18, 20, 22)
        hero_box.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.addStretch(1)
        self.refresh_btn = widgets.icon_button("refresh", theme.TEXT_FAINT,
                                               tooltip="Check again")
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        top_row.addWidget(self.refresh_btn)
        hero_box.addLayout(top_row)

        self.hero_icon = HeroIcon()
        hero_box.addWidget(self.hero_icon, 0, Qt.AlignHCenter)
        hero_box.addSpacing(10)

        self.headline = QLabel("Checking…")
        self.headline.setObjectName("HeroHeadline")
        self.headline.setAlignment(Qt.AlignHCenter)
        self.headline.setWordWrap(True)
        hero_box.addWidget(self.headline)

        self.subline = QLabel("")
        self.subline.setObjectName("HeroSubline")
        self.subline.setAlignment(Qt.AlignHCenter)
        self.subline.setWordWrap(True)
        hero_box.addWidget(self.subline)
        root.addWidget(hero)

        # -- actions ----------------------------------------------------------
        self.play_btn = widgets.PlayButton("PLAY")
        self.play_btn.setIcon(icons.icon("play", theme.ON_ACCENT, 20))
        self.play_btn.clicked.connect(self.play_clicked.emit)
        root.addWidget(self.play_btn)

        self.save_btn = widgets.make_button("Save my progress now", "ghost",
                                            "upload-cloud", height=42)
        self.save_btn.setToolTip("Share your current save without launching the game")
        self.save_btn.clicked.connect(self.save_clicked.emit)
        root.addWidget(self.save_btn)

        # -- feed -------------------------------------------------------------
        section = QLabel(FEED_TITLE)
        section.setObjectName("SectionLabel")
        root.addSpacing(2)
        root.addWidget(section)

        feed_card = QFrame()
        feed_card.setObjectName("Card")
        feed_wrap = QVBoxLayout(feed_card)
        feed_wrap.setContentsMargins(6, 6, 6, 6)

        self.feed_scroll = QScrollArea()
        self.feed_scroll.setWidgetResizable(True)
        self.feed_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.feed_body = QWidget()
        self.feed_body.setStyleSheet("background: transparent;")
        self.feed_box = QVBoxLayout(self.feed_body)
        self.feed_box.setContentsMargins(10, 8, 10, 8)
        self.feed_box.setSpacing(0)
        self.feed_scroll.setWidget(self.feed_body)
        feed_wrap.addWidget(self.feed_scroll)
        feed_card.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        root.addWidget(feed_card, 1)

        # -- footer -----------------------------------------------------------
        footer = QHBoxLayout()
        self.conn_dot = QLabel("●")
        self.conn_dot.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 9px;")
        self.conn_text = QLabel("")
        self.conn_text.setObjectName("FooterText")
        version = QLabel(f"v{__version__}")
        version.setObjectName("FooterText")
        footer.addWidget(self.conn_dot)
        footer.addWidget(self.conn_text)
        footer.addStretch(1)
        footer.addWidget(version)
        root.addLayout(footer)

        # Relative times ("2 h ago") drift; refresh them once a minute.
        self._clock = QTimer(self)
        self._clock.setInterval(60_000)
        self._clock.timeout.connect(self._rerender)
        self._clock.start()

    # -- state ----------------------------------------------------------------
    def set_player_name(self, name):
        self._me = name or ""

    def set_checking(self):
        if self._phase == "idle":
            self.hero_icon.show_spinner()
            self.headline.setText("Checking the shared folder…")
            self.subline.setText("Looking for a newer save from your friends.")

    def set_status(self, snapshot):
        self._snapshot = snapshot
        self._rerender()

    def set_phase(self, phase):
        self._phase = phase
        busy = phase != "idle"
        self.play_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)

        if phase == "idle":
            self.play_btn.setText("PLAY")
            self._rerender()
            return

        labels = {
            "checking": ("CHECKING…", None),
            "launching": ("LAUNCHING…", None),
            "waiting": ("LAUNCHING…", None),
            "ingame": ("IN GAME", None),
            "pushing": ("SHARING…", None),
        }
        self.play_btn.setText(labels.get(phase, ("PLAY",))[0])

        if phase == "checking":
            self.hero_icon.show_spinner()
            self.headline.setText("Checking for a newer save…")
            self.subline.setText("Making sure you start from the latest world.")
        elif phase == "launching":
            self.hero_icon.show_spinner()
            self.headline.setText("Launching Dragonwilds…")
            self.subline.setText("Handing you over to Steam.")
        elif phase == "waiting":
            self.hero_icon.show_spinner()
            self.headline.setText("Waiting for the game to start…")
            self.subline.setText("This can take a minute while Steam warms up.")
        elif phase == "ingame":
            self.hero_icon.show_pulse()
            self.headline.setText("You're in the wilds")
            self.subline.setText("Your progress is shared automatically when you close the game.")
        elif phase == "pushing":
            self.hero_icon.show_spinner()
            self.headline.setText("Sharing your progress…")
            self.subline.setText("Uploading your save to the shared folder.")

    # -- rendering --------------------------------------------------------------
    def _rerender(self):
        if self._phase != "idle" or self._snapshot is None:
            return
        snap = self._snapshot

        if snap.kind == "error":
            self.hero_icon.show_icon("alert", theme.RED_HOVER)
            self.headline.setText("Something went wrong")
            self.subline.setText("Couldn't check the shared folder. Try again in a moment — "
                                 "details are in Settings → Open log folder.")
            self._set_conn(theme.RED, "Shared folder unreachable")
        elif snap.kind == "folder_missing":
            self.hero_icon.show_icon("folder", theme.AMBER)
            self.headline.setText("Shared folder not found")
            self.subline.setText("Is your cloud drive running? If the folder moved, "
                                 "update it in Settings.")
            self._set_conn(theme.AMBER, "Shared folder unreachable")
        elif snap.kind == "no_shared":
            self.hero_icon.show_icon("sparkle", theme.ACCENT)
            self.headline.setText("A fresh world awaits")
            self.subline.setText("No one has shared a save yet — hit Play and carve the first path.")
            self._set_conn(theme.ACCENT, "Shared folder connected")
        elif snap.kind == "behind":
            editor = self._display_name(snap.last_editor)
            self.hero_icon.show_icon("download-cloud", theme.AMBER)
            self.headline.setText(f"New save from {editor}")
            self.subline.setText(f"v{snap.shared_version} · {fmt.humanize(snap.timestamp)} — "
                                 f"Play will pick it up automatically.")
            self._set_conn(theme.ACCENT, "Shared folder connected")
        else:  # up_to_date
            editor = self._display_name(snap.last_editor)
            self.hero_icon.show_icon("check-circle", theme.ACCENT)
            self.headline.setText("You're up to date")
            self.subline.setText(f"v{snap.shared_version} · last played by {editor} "
                                 f"{fmt.humanize(snap.timestamp)}.")
            self._set_conn(theme.ACCENT, "Shared folder connected")

        self._render_feed(snap.history if getattr(snap, "history", None) else [])

    def _display_name(self, editor):
        if not editor:
            return "a friend"
        return "you" if editor == self._me else editor

    def _set_conn(self, color, text):
        self.conn_dot.setStyleSheet(f"color: {color}; font-size: 9px;")
        self.conn_text.setText(text)

    def _render_feed(self, history):
        while self.feed_box.count():
            item = self.feed_box.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not history:
            empty = QWidget()
            box = QVBoxLayout(empty)
            box.setContentsMargins(16, 26, 16, 26)
            box.setSpacing(6)
            ic = QLabel()
            ic.setPixmap(icons.pixmap("dragon", theme.TEXT_FAINT, 26))
            ic.setAlignment(Qt.AlignHCenter)
            box.addWidget(ic)
            t1 = QLabel("No sessions yet")
            t1.setAlignment(Qt.AlignHCenter)
            t1.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 13px; font-weight: 600;")
            box.addWidget(t1)
            t2 = QLabel("Once someone plays, the world's story shows up here.")
            t2.setAlignment(Qt.AlignHCenter)
            t2.setWordWrap(True)
            t2.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11.5px;")
            box.addWidget(t2)
            self.feed_box.addWidget(empty)
            self.feed_box.addStretch(1)
            return

        for i, entry in enumerate(reversed(history)):
            self.feed_box.addWidget(self._feed_row(entry, first=(i == 0)))
        self.feed_box.addStretch(1)

    def _feed_row(self, entry, first=False):
        row = QWidget()
        if not first:
            row.setStyleSheet(f"border-top: 1px solid {theme.BORDER_SOFT};")
        lay = QHBoxLayout(row)
        lay.setContentsMargins(6, 9, 6, 9)
        lay.setSpacing(10)

        editor = entry.get("editor") or entry.get("last_editor") or "?"
        lay.addWidget(widgets.Avatar(editor, 30))

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel("You" if editor == self._me else editor)
        name.setObjectName("FeedName")
        name.setStyleSheet("border: none;")
        meta = QLabel(f"shared v{entry.get('version', '?')}")
        meta.setObjectName("FeedMeta")
        meta.setStyleSheet("border: none;")
        col.addWidget(name)
        col.addWidget(meta)
        lay.addLayout(col)
        lay.addStretch(1)

        when = QLabel(fmt.humanize(entry.get("timestamp", "")))
        when.setObjectName("FeedTime")
        when.setStyleSheet("border: none;")
        lay.addWidget(when)
        return row
