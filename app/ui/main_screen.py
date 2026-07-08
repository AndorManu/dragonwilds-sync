"""The home screen: world switcher, status hero, Play, and the session feed."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu, QScrollArea,
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
        self._amber_dot_wrap = self._center(widgets.PulsingDot(18, theme.AMBER))
        self._stack.addWidget(self._icon_label)
        self._stack.addWidget(self._spinner_wrap)
        self._stack.addWidget(self._dot_wrap)
        self._stack.addWidget(self._amber_dot_wrap)

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

    def show_pulse(self, amber=False):
        self._tint(theme.AMBER if amber else theme.ACCENT)
        self._stack.setCurrentWidget(self._amber_dot_wrap if amber else self._dot_wrap)


class MainPage(QWidget):
    play_clicked = Signal()
    save_clicked = Signal()
    refresh_clicked = Signal()
    invite_clicked = Signal()
    world_selected = Signal(str)          # world_id
    add_world_clicked = Signal()
    backups_clicked = Signal()
    next_claim_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = None               # WorldStatus
        self._phase = "idle"
        self._me = ""
        self._worlds = []
        self._active_id = None

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 4, 24, 16)
        root.setSpacing(12)

        # -- header: world switcher + invite ---------------------------------
        header = QHBoxLayout()
        header.setSpacing(8)
        self.world_btn = widgets.make_button("", "subtle", height=32)
        self.world_btn.setStyleSheet("font-size: 14px; font-weight: 650; text-align: left;")
        self.world_btn.clicked.connect(self._open_world_menu)
        header.addWidget(self.world_btn)
        header.addStretch(1)
        self.invite_btn = widgets.make_button("Invite friends", "ghost",
                                              "user-plus", height=32)
        self.invite_btn.clicked.connect(self.invite_clicked.emit)
        header.addWidget(self.invite_btn)
        root.addLayout(header)

        # -- hero card ----------------------------------------------------------
        hero = QFrame()
        hero.setObjectName("Card")
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(20, 14, 20, 22)
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

        # -- actions ----------------------------------------------------------------
        self.play_btn = widgets.PlayButton("PLAY")
        self.play_btn.setIcon(icons.icon("play", theme.ON_ACCENT, 20))
        self.play_btn.clicked.connect(self.play_clicked.emit)
        root.addWidget(self.play_btn)

        self.save_btn = widgets.make_button("Save my progress now", "ghost",
                                            "upload-cloud", height=40)
        self.save_btn.setToolTip("Share your current save without launching the game")
        self.save_btn.clicked.connect(self.save_clicked.emit)
        root.addWidget(self.save_btn)

        # -- turn claim row ------------------------------------------------------------
        claim_row = QHBoxLayout()
        claim_row.setSpacing(8)
        self.claim_label = QLabel("")
        self.claim_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        claim_row.addWidget(self.claim_label)
        claim_row.addStretch(1)
        self.claim_btn = widgets.make_button("I've got next", "subtle", "flag", height=28)
        self.claim_btn.clicked.connect(self.next_claim_clicked.emit)
        claim_row.addWidget(self.claim_btn)
        root.addLayout(claim_row)

        # -- feed --------------------------------------------------------------------------
        section = QLabel(FEED_TITLE)
        section.setObjectName("SectionLabel")
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

        # -- footer ------------------------------------------------------------------------
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

        self._clock = QTimer(self)
        self._clock.setInterval(60_000)
        self._clock.timeout.connect(self._rerender)
        self._clock.start()

    # -- world switcher ------------------------------------------------------------
    def set_worlds(self, worlds, active_id):
        self._worlds = worlds
        self._active_id = active_id
        active = next((w for w in worlds if w["id"] == active_id), None)
        name = active["world_name"] if active else "No world"
        self.world_btn.setText(f"{name}  ⌄")

    def _open_world_menu(self):
        menu = QMenu(self)
        for w in self._worlds:
            action = menu.addAction(w["world_name"])
            if w["id"] == self._active_id:
                action.setIcon(icons.icon("check", theme.ACCENT, 14))
            action.triggered.connect(
                lambda _=False, wid=w["id"]: self.world_selected.emit(wid))
        menu.addSeparator()
        add = menu.addAction(icons.icon("plus", theme.TEXT_DIM, 14), "Add a world…")
        add.triggered.connect(self.add_world_clicked.emit)
        backups = menu.addAction(icons.icon("archive", theme.TEXT_DIM, 14), "Backups…")
        backups.triggered.connect(self.backups_clicked.emit)
        menu.exec(self.world_btn.mapToGlobal(self.world_btn.rect().bottomLeft()))

    # -- state ---------------------------------------------------------------------
    def set_player_name(self, name):
        self._me = name or ""

    def set_checking(self):
        if self._phase == "idle":
            self.hero_icon.show_spinner()
            self.headline.setText("Checking the shared folder…")
            self.subline.setText("Looking for a newer save from your friends.")

    def set_status(self, status):
        self._status = status
        self._rerender()

    def set_phase(self, phase):
        self._phase = phase
        busy = phase != "idle"
        self.play_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        self.refresh_btn.setEnabled(not busy)
        self.world_btn.setEnabled(not busy)
        self.claim_btn.setEnabled(not busy)

        if phase == "idle":
            self.play_btn.setText("PLAY")
            self._rerender()
            return

        labels = {"checking": "CHECKING…", "launching": "LAUNCHING…",
                  "waiting": "LAUNCHING…", "ingame": "IN GAME",
                  "pushing": "SHARING…"}
        self.play_btn.setText(labels.get(phase, "PLAY"))

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

    # -- rendering ---------------------------------------------------------------------
    def _rerender(self):
        if self._phase != "idle" or self._status is None:
            return
        status = self._status
        snap = status.snapshot

        self._render_claim(status.next_claim)

        if status.newer_app_needed:
            self.hero_icon.show_icon("alert", theme.AMBER)
            self.headline.setText("This world needs a newer app")
            self.subline.setText("A friend shared a save with a newer version of "
                                 "Dragonwilds Sync. Update your app before playing "
                                 "so nothing gets scrambled.")
            self.play_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self._set_conn(theme.AMBER, "App update needed")
            self._render_feed(getattr(snap, "history", None) or [])
            return

        if status.playing:
            who = status.playing
            minutes = int((who.get("age_s") or 0) // 60)
            if minutes < 1:
                since = "just now"
            elif minutes < 120:
                since = f"{minutes} min ago"
            else:
                since = f"{minutes // 60} h ago"
            self.hero_icon.show_pulse(amber=True)
            self.headline.setText(f"{who['player']} is in the wilds right now")
            self.subline.setText(f"Started {since}. Best wait for their save — "
                                 f"you'll see it land here.")
            self._set_conn(theme.ACCENT, "Shared folder connected")
            self._render_feed(getattr(snap, "history", None) or [])
            return

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

        self._render_feed(getattr(snap, "history", None) or [])

    def _render_claim(self, claim):
        if claim and claim.get("player") == self._me:
            self.claim_label.setText("You have the next turn.")
            self.claim_btn.setText("Release claim")
            self.claim_btn.setEnabled(self._phase == "idle")
        elif claim:
            emoji = claim.get("emoji") or ""
            self.claim_label.setText(f"{emoji} {claim['player']} has next.".strip())
            self.claim_btn.setText("I've got next")
            self.claim_btn.setEnabled(False)
        else:
            self.claim_label.setText("")
            self.claim_btn.setText("I've got next")
            self.claim_btn.setEnabled(self._phase == "idle")

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
        lay.addWidget(widgets.Avatar(editor, 30, emoji=entry.get("emoji", ""),
                                     color=entry.get("color") or None),
                      0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel("You" if editor == self._me else editor)
        name.setObjectName("FeedName")
        name.setStyleSheet("border: none;")
        meta_text = f"shared v{entry.get('version', '?')}"
        duration = entry.get("duration_s")
        if duration:
            meta_text += f" · {self._fmt_duration(duration)} session"
        meta = QLabel(meta_text)
        meta.setObjectName("FeedMeta")
        meta.setStyleSheet("border: none;")
        col.addWidget(name)
        col.addWidget(meta)
        note = entry.get("note")
        if note:
            note_label = QLabel(f"“{note}”")
            note_label.setWordWrap(True)
            note_label.setStyleSheet(
                f"border: none; color: {theme.TEXT_DIM}; font-size: 12px; font-style: italic;")
            col.addWidget(note_label)
        lay.addLayout(col, 1)

        when = QLabel(fmt.humanize(entry.get("timestamp", "")))
        when.setObjectName("FeedTime")
        when.setStyleSheet("border: none;")
        lay.addWidget(when, 0, Qt.AlignTop)
        return row

    @staticmethod
    def _fmt_duration(seconds):
        seconds = int(seconds)
        if seconds < 90 * 60:
            return f"{max(1, seconds // 60)} min"
        return f"{seconds / 3600:.1f} h"
