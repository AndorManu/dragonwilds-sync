"""The home screen: a cinematic world banner, the status readout, the
showpiece PLAY button, and the session feed."""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QMenu, QPushButton,
                               QScrollArea, QSizePolicy, QStackedWidget,
                               QVBoxLayout, QWidget)

from .. import __version__
from . import format as fmt
from . import icons, theme, widgets
from .banner import WorldBanner

FEED_TITLE = "RECENT SESSIONS"


class HeroIcon(QFrame):
    """Small status medallion: a static icon, a spinner, or a pulse."""

    def __init__(self, size=44, parent=None):
        super().__init__(parent)
        self._size = size
        self.setFixedSize(size, size)
        self._stack = QStackedWidget(self)
        box = QVBoxLayout(self)
        box.setContentsMargins(0, 0, 0, 0)
        box.addWidget(self._stack)

        self._icon_label = QLabel()
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setStyleSheet("background: transparent; border: none;")
        self._spinner_wrap = self._center(widgets.Spinner(22))
        self._dot_wrap = self._center(widgets.PulsingDot(15))
        self._amber_dot_wrap = self._center(widgets.PulsingDot(15, theme.AMBER))
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
        rad = self._size // 2
        self.setStyleSheet(
            f"HeroIcon {{ background: rgba({r},{g},{b},0.14);"
            f"border: 1px solid rgba({r},{g},{b},0.30); border-radius: {rad}px; }}")

    def show_icon(self, name, color):
        self._icon_label.setPixmap(icons.pixmap(name, color, 22))
        self._tint(color)
        self._stack.setCurrentWidget(self._icon_label)

    def show_spinner(self):
        self._tint(theme.ACCENT)
        self._stack.setCurrentWidget(self._spinner_wrap)

    def show_pulse(self, amber=False):
        self._tint(theme.AMBER if amber else theme.ACCENT)
        self._stack.setCurrentWidget(self._amber_dot_wrap if amber else self._dot_wrap)


class BannerHeader(QWidget):
    """The world-art banner with overlaid title, controls, and a status pill."""

    world_menu_requested = Signal()
    refresh_requested = Signal()
    invite_requested = Signal()

    def __init__(self, height=158, parent=None):
        super().__init__(parent)
        self.setFixedHeight(height)
        self.banner = WorldBanner(height, self)

        self.overlay = QWidget(self)
        self.overlay.setStyleSheet("background: transparent;")
        ov = QVBoxLayout(self.overlay)
        ov.setContentsMargins(18, 12, 12, 14)
        ov.setSpacing(0)

        top = QHBoxLayout()
        top.setSpacing(6)
        top.addStretch(1)
        self.refresh_btn = widgets.icon_button("refresh", theme.GOLD_TEXT,
                                               tooltip="Check again")
        self.refresh_btn.clicked.connect(self.refresh_requested.emit)
        self.invite_btn = widgets.icon_button("user-plus", theme.GOLD_TEXT,
                                              tooltip="Invite friends")
        self.invite_btn.clicked.connect(self.invite_requested.emit)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.invite_btn)
        ov.addLayout(top)
        ov.addStretch(1)

        self.title_btn = QPushButton("World")
        self.title_btn.setObjectName("WorldTitle")
        self.title_btn.setCursor(Qt.PointingHandCursor)
        self.title_btn.setFlat(True)
        self.title_btn.setStyleSheet(
            "QPushButton#WorldTitle { background: transparent; border: none;"
            "color: #FFFFFF; text-align: left; padding: 0; }")
        f = QFont(theme.deco_family())
        f.setPixelSize(29)
        f.setWeight(QFont.Bold)
        self.title_btn.setFont(f)
        self.title_btn.clicked.connect(self.world_menu_requested.emit)
        ov.addWidget(self.title_btn)

        pill_row = QHBoxLayout()
        pill_row.setSpacing(8)
        self.pill = QLabel("")
        self.pill.setObjectName("HeroPill")
        self.pill.setVisible(False)
        pill_row.addWidget(self.pill)
        pill_row.addStretch(1)
        ov.addSpacing(5)
        ov.addLayout(pill_row)

    def resizeEvent(self, e):
        self.banner.setGeometry(0, 0, self.width(), self.height())
        self.overlay.setGeometry(0, 0, self.width(), self.height())
        self.overlay.raise_()
        super().resizeEvent(e)

    def set_world(self, name, accent):
        self.banner.set_world(name, accent)
        self.title_btn.setText(f"{name}  ⌄")

    def set_pill(self, text, color):
        if not text:
            self.pill.setVisible(False)
            return
        c = color.lstrip("#")
        r, g, b = int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
        self.pill.setText(text)
        self.pill.setStyleSheet(
            f"#HeroPill {{ background: rgba({r},{g},{b},0.18);"
            f"color: {color}; border: 1px solid rgba({r},{g},{b},0.45);"
            f"border-radius: 11px; padding: 3px 11px; }}")
        self.pill.setVisible(True)


class MainPage(QWidget):
    play_clicked = Signal()
    save_clicked = Signal()
    refresh_clicked = Signal()
    invite_clicked = Signal()
    world_selected = Signal(str)
    add_world_clicked = Signal()
    backups_clicked = Signal()
    next_claim_clicked = Signal()
    pass_turn_clicked = Signal()
    update_clicked = Signal()
    characters_clicked = Signal()
    grimoire_clicked = Signal()
    saga_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._status = None
        self._phase = "idle"
        self._me = ""
        self._worlds = []
        self._active_id = None
        self._grimoire = False

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- banner hero ----------------------------------------------------
        self.header = BannerHeader()
        self.header.world_menu_requested.connect(self._open_world_menu)
        self.header.refresh_requested.connect(self.refresh_clicked.emit)
        self.header.invite_requested.connect(self.invite_clicked.emit)
        root.addWidget(self.header)

        body = QWidget()
        body_box = QVBoxLayout(body)
        body_box.setContentsMargins(24, 14, 24, 16)
        body_box.setSpacing(13)
        root.addWidget(body, 1)

        # -- update bar (hidden until an update is published) ---------------
        self.update_bar = QFrame()
        self.update_bar.setObjectName("UpdateBar")
        self.update_bar.setStyleSheet(
            f"#UpdateBar {{ background: rgba(232,162,61,0.12);"
            f"border: 1px solid rgba(232,162,61,0.40); border-radius: 10px; }}")
        ub = QHBoxLayout(self.update_bar)
        ub.setContentsMargins(12, 8, 8, 8)
        ub.setSpacing(9)
        ub_icon = QLabel()
        ub_icon.setPixmap(icons.pixmap("rocket", theme.EMBER, 17))
        ub_icon.setStyleSheet("background: transparent; border: none;")
        ub.addWidget(ub_icon, 0, Qt.AlignVCenter)
        self.update_label = QLabel("")
        self.update_label.setWordWrap(True)
        self.update_label.setStyleSheet(
            f"background: transparent; border: none; color: {theme.GOLD_TEXT}; font-size: 12px;")
        ub.addWidget(self.update_label, 1)
        update_btn = widgets.make_button("Update", "primary", height=30)
        update_btn.clicked.connect(self.update_clicked.emit)
        ub.addWidget(update_btn, 0, Qt.AlignVCenter)
        self.update_bar.setVisible(False)
        body_box.addWidget(self.update_bar)

        # -- status readout -------------------------------------------------
        status_row = QHBoxLayout()
        status_row.setSpacing(13)
        self.hero_icon = HeroIcon(44)
        status_row.addWidget(self.hero_icon, 0, Qt.AlignVCenter)
        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        self.headline = QLabel("Checking…")
        self.headline.setObjectName("HeroHeadline")
        self.headline.setWordWrap(True)
        self.subline = QLabel("")
        self.subline.setObjectName("HeroSubline")
        self.subline.setWordWrap(True)
        text_col.addWidget(self.headline)
        text_col.addWidget(self.subline)
        status_row.addLayout(text_col, 1)
        body_box.addLayout(status_row)

        # -- actions --------------------------------------------------------
        self.play_btn = widgets.PlayButton("PLAY")
        self.play_btn.setIcon(icons.icon("play", theme.ON_ACCENT, 20))
        self.play_btn.clicked.connect(self.play_clicked.emit)
        body_box.addWidget(self.play_btn)

        self.save_btn = widgets.make_button("Save my progress now", "ghost",
                                            "upload-cloud", height=40)
        self.save_btn.setToolTip("Share your current save without launching the game")
        self.save_btn.clicked.connect(self.save_clicked.emit)
        body_box.addWidget(self.save_btn)

        # -- turn claim -----------------------------------------------------
        claim_row = QHBoxLayout()
        claim_row.setSpacing(8)
        self.claim_label = QLabel("")
        self.claim_label.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        claim_row.addWidget(self.claim_label)
        claim_row.addStretch(1)
        self.pass_btn = widgets.make_button("Pass turn", "subtle", "send", height=28)
        self.pass_btn.setToolTip("Ping a friend that it's their turn")
        self.pass_btn.clicked.connect(self.pass_turn_clicked.emit)
        claim_row.addWidget(self.pass_btn)
        self.claim_btn = widgets.make_button("I've got next", "subtle", "flag", height=28)
        self.claim_btn.clicked.connect(self.next_claim_clicked.emit)
        claim_row.addWidget(self.claim_btn)
        body_box.addLayout(claim_row)

        # -- feed -----------------------------------------------------------
        section = QLabel(FEED_TITLE)
        section.setObjectName("SectionLabel")
        body_box.addWidget(section)

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
        body_box.addWidget(feed_card, 1)

        # -- footer ---------------------------------------------------------
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
        body_box.addLayout(footer)

        self._clock = QTimer(self)
        self._clock.setInterval(60_000)
        self._clock.timeout.connect(self._rerender)
        self._clock.start()

    # -- world switcher ------------------------------------------------------
    def set_worlds(self, worlds, active_id):
        self._worlds = worlds
        self._active_id = active_id
        active = next((w for w in worlds if w["id"] == active_id), None)
        name = active["world_name"] if active else "No world"
        accent = (active or {}).get("accent") or fmt.name_color(name)
        self.header.set_world(name, accent)

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
        chars = menu.addAction(icons.icon("dragon", theme.TEXT_DIM, 14), "Characters…")
        chars.triggered.connect(self.characters_clicked.emit)
        saga = menu.addAction(icons.icon("map", theme.TEXT_DIM, 14), "The Saga…")
        saga.triggered.connect(self.saga_clicked.emit)
        backups = menu.addAction(icons.icon("archive", theme.TEXT_DIM, 14), "Backups…")
        backups.triggered.connect(self.backups_clicked.emit)
        if self._grimoire:
            menu.addSeparator()
            secret = menu.addAction(icons.icon("sparkle", theme.EMBER, 14),
                                    "The Dragon's Bargain…")
            secret.triggered.connect(self.grimoire_clicked.emit)
        menu.exec(self.header.title_btn.mapToGlobal(
            self.header.title_btn.rect().bottomLeft()))

    def set_grimoire(self, unlocked: bool):
        self._grimoire = bool(unlocked)

    # -- update bar ----------------------------------------------------------
    def show_update_bar(self, version, published_by):
        who = f" from {published_by}" if published_by else ""
        self.update_label.setText(f"Version {version} is ready{who}.")
        self.update_bar.setVisible(True)

    def hide_update_bar(self):
        self.update_bar.setVisible(False)

    # -- state ---------------------------------------------------------------
    def set_player_name(self, name):
        self._me = name or ""

    def set_checking(self):
        if self._phase == "idle":
            self.hero_icon.show_spinner()
            self.headline.setText("Reading the shared folder…")
            self.subline.setText("Looking for a newer save from your friends.")

    def set_status(self, status):
        self._status = status
        self._rerender()

    def set_phase(self, phase):
        self._phase = phase
        busy = phase != "idle"
        self.play_btn.setEnabled(not busy)
        self.save_btn.setEnabled(not busy)
        self.header.refresh_btn.setEnabled(not busy)
        self.claim_btn.setEnabled(not busy)
        self.pass_btn.setEnabled(not busy)

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
            self._say("Checking for a newer save…",
                      "Making sure you start from the latest world.")
            self.header.set_pill("Syncing", theme.EMBER)
        elif phase == "launching":
            self.hero_icon.show_spinner()
            self._say("Launching Dragonwilds…", "Handing you over to Steam.")
            self.header.set_pill("Launching", theme.EMBER)
        elif phase == "waiting":
            self.hero_icon.show_spinner()
            self._say("Waiting for the game to start…",
                      "This can take a minute while Steam warms up.")
            self.header.set_pill("Launching", theme.EMBER)
        elif phase == "ingame":
            self.hero_icon.show_pulse()
            self._say("You're in the wilds",
                      "Your progress is shared automatically when you close the game.")
            self.header.set_pill("Playing", theme.ACCENT)
        elif phase == "pushing":
            self.hero_icon.show_spinner()
            self._say("Sharing your progress…",
                      "Uploading your save to the shared folder.")
            self.header.set_pill("Sharing", theme.EMBER)

    def _say(self, headline, subline):
        self.headline.setText(headline)
        self.subline.setText(subline)

    # -- rendering -----------------------------------------------------------
    def _rerender(self):
        if self._phase != "idle" or self._status is None:
            return
        status = self._status
        snap = status.snapshot
        self._render_claim(status.next_claim)

        if status.newer_app_needed:
            self.hero_icon.show_icon("alert", theme.AMBER)
            self._say("This world needs a newer app",
                      "A friend shared a save with a newer version of Dragonwilds "
                      "Sync. Update your app before playing so nothing gets scrambled.")
            self.play_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
            self.header.set_pill("Update needed", theme.AMBER)
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
            as_char = f" as {who['character']}" if who.get("character") else ""
            self._say(f"{who['player']} is in the wilds right now",
                      f"Playing{as_char} — started {since}. Best wait for their "
                      f"save; you'll see it land here.")
            self.header.set_pill(f"{who['player']} playing", theme.AMBER)
            self._set_conn(theme.ACCENT, "Shared folder connected")
            self._render_feed(getattr(snap, "history", None) or [])
            return

        if snap.kind == "error":
            self.hero_icon.show_icon("alert", theme.RED_HOVER)
            self._say("Something went wrong",
                      "Couldn't read the shared folder. Try again in a moment — "
                      "details are in Settings → Open log folder.")
            self.header.set_pill("Unreachable", theme.RED_HOVER)
            self._set_conn(theme.RED, "Shared folder unreachable")
        elif snap.kind == "folder_missing":
            self.hero_icon.show_icon("folder", theme.AMBER)
            self._say("Shared folder not found",
                      "Is your cloud drive running? If the folder moved, update it in Settings.")
            self.header.set_pill("Offline", theme.AMBER)
            self._set_conn(theme.AMBER, "Shared folder unreachable")
        elif snap.kind == "no_shared":
            self.hero_icon.show_icon("sparkle", theme.EMBER)
            self._say("A fresh world awaits",
                      "No one has shared a save yet — hit Play and carve the first path.")
            self.header.set_pill("New world", theme.EMBER)
            self._set_conn(theme.ACCENT, "Shared folder connected")
        elif snap.kind == "behind":
            editor = self._display_name(snap.last_editor)
            self.hero_icon.show_icon("download-cloud", theme.AMBER)
            self._say(f"New save from {editor}",
                      f"v{snap.shared_version} · {fmt.humanize(snap.timestamp)} — "
                      f"Play will pick it up automatically.")
            self.header.set_pill("New save", theme.AMBER)
            self._set_conn(theme.ACCENT, "Shared folder connected")
        else:  # up_to_date
            editor = self._display_name(snap.last_editor)
            self.hero_icon.show_icon("check-circle", theme.ACCENT)
            self._say("You're up to date",
                      f"v{snap.shared_version} · last played by {editor} "
                      f"{fmt.humanize(snap.timestamp)}.")
            self.header.set_pill("Up to date", theme.ACCENT)
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
            box.setContentsMargins(16, 24, 16, 24)
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
                                     color=entry.get("color") or None,
                                     portrait=entry.get("portrait", "")),
                      0, Qt.AlignTop)

        col = QVBoxLayout()
        col.setSpacing(1)
        name = QLabel("You" if editor == self._me else editor)
        name.setObjectName("FeedName")
        name.setStyleSheet("border: none;")
        meta_text = f"shared v{entry.get('version', '?')}"
        if entry.get("character"):
            meta_text = f"as {entry['character']} · " + meta_text
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
                f"border: none; color: {theme.GOLD_TEXT}; font-family: '{theme.voice_family()}';"
                f"font-size: 13px; font-style: italic;")
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
