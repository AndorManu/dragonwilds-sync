"""Add a game: every supported game, the ones installed on this PC first.

Each row is a small poster of the game's scene with its name in the game's
own typeface. Steam installs are detected from the library manifests, so
the games you actually own float to the top.
"""

import threading
import webbrowser

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QHBoxLayout, QLabel, QLineEdit, QScrollArea,
                               QVBoxLayout, QWidget)

from ..core import games, steam
from . import gamethemes, icons, theme, widgets
from .library_page import game_font, game_thumb

ROW_H = 74
THUMB_W = 104
REQUEST_URL = "https://github.com/AndorManu/worldsync/issues/new?labels=game-request&title=Game+request:+"


class GameRow(QWidget):
    clicked = Signal(str)

    def __init__(self, profile, installed: bool, in_library: bool, parent=None):
        super().__init__(parent)
        self.profile = profile
        self.installed = installed
        self.in_library = in_library
        self._hover = False
        self.setFixedHeight(ROW_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.profile.id)

    def event(self, e):
        if e.type() in (e.Type.HoverEnter, e.Type.HoverLeave):
            self._hover = e.type() == e.Type.HoverEnter
            self.update()
        return super().event(e)

    def _badge(self, p, x, y, text, color):
        f = QFont(self.font().family())
        f.setPixelSize(9)
        f.setWeight(QFont.Bold)
        f.setLetterSpacing(QFont.AbsoluteSpacing, 0.6)
        p.setFont(f)
        w = p.fontMetrics().horizontalAdvance(text) + 14
        c = QColor(color)
        fill = QColor(c)
        fill.setAlphaF(0.16)
        p.setPen(QPen(c, 1))
        p.setBrush(fill)
        p.drawRoundedRect(QRectF(x, y, w, 17), 8.5, 8.5)
        p.drawText(QRectF(x, y, w, 17), Qt.AlignCenter, text)
        return x + w + 6

    def paintEvent(self, e):
        tok = gamethemes.get(self.profile.id).tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        p.setPen(QPen(QColor(tok["ACCENT"] if self._hover else theme.BORDER_SOFT), 1.2))
        p.setBrush(QColor(theme.SURFACE_2 if self._hover else theme.SURFACE))
        p.drawRoundedRect(r, 12, 12)

        thumb = QRectF(8, 8, THUMB_W, ROW_H - 16)
        clip = QPainterPath()
        clip.addRoundedRect(thumb, 8, 8)
        p.save()
        p.setClipPath(clip)
        p.drawPixmap(thumb.toRect(), game_thumb(self.profile.id, THUMB_W * 2, (ROW_H - 16) * 2))
        p.restore()

        x = THUMB_W + 22
        p.setPen(QColor("#FFFFFF"))
        p.setFont(game_font(self.profile.id, 15))
        p.drawText(QRectF(x, 10, r.width() - x - 10, 22), Qt.AlignLeft | Qt.AlignVCenter,
                   self.profile.name)
        f = QFont(self.font())
        f.setPixelSize(12)
        p.setFont(f)
        p.setPen(QColor(theme.TEXT_DIM))
        p.drawText(QRectF(x, 31, r.width() - x - 10, 18), Qt.AlignLeft | Qt.AlignVCenter,
                   self.profile.tagline)
        bx = x
        if self.in_library:
            bx = self._badge(p, bx, 50, "IN LIBRARY", theme.TEXT_DIM)
        if self.installed:
            bx = self._badge(p, bx, 50, "INSTALLED", tok["ACCENT"])
        if not self.profile.verified:
            self._badge(p, bx, 50, "BETA", tok["EMBER"])
        p.end()


class AddGamePage(QWidget):
    game_chosen = Signal(str)
    back_requested = Signal()
    installed_ready = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._installed: set[str] = set()
        self._library: set[str] = set()
        self._rows: list[GameRow] = []

        root = QVBoxLayout(self)
        root.setContentsMargins(24, 6, 24, 18)
        root.setSpacing(12)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        self.title = QLabel("Add a game")
        self.title.setStyleSheet("font-size: 20px; font-weight: 650;")
        header.addWidget(self.title)
        header.addStretch(1)
        root.addLayout(header)

        self.sub = QLabel("Pick the game your group shares a world in. "
                          "Games installed through Steam are at the top.")
        self.sub.setWordWrap(True)
        self.sub.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
        root.addWidget(self.sub)

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search games")
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(38)
        self.search.addAction(icons.icon("search", theme.TEXT_FAINT, 16),
                              QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        root.addWidget(self.search)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self.list_box = QVBoxLayout(holder)
        self.list_box.setContentsMargins(0, 0, 4, 0)
        self.list_box.setSpacing(8)
        self.list_box.addStretch(1)
        scroll.setWidget(holder)
        root.addWidget(scroll, 1)

        self.empty = QLabel("No game matches that search.")
        self.empty.setAlignment(Qt.AlignCenter)
        self.empty.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 12.5px;")
        self.empty.setVisible(False)
        root.addWidget(self.empty)

        foot = QHBoxLayout()
        foot.addStretch(1)
        req = widgets.make_button("Missing a game? Ask for it", "subtle", "external", height=28)
        req.clicked.connect(lambda: webbrowser.open(REQUEST_URL))
        foot.addWidget(req)
        root.addLayout(foot)

        self.installed_ready.connect(self._on_installed)

    # -- public -----------------------------------------------------------------
    def open(self, library_ids, first_run=False):
        self._library = set(library_ids)
        self.title.setText("Pick your first game" if first_run else "Add a game")
        self.search.clear()
        self._rebuild()
        threading.Thread(target=self._detect, daemon=True, name="steam-scan").start()

    # -- internals --------------------------------------------------------------
    def _detect(self):
        try:
            ids = steam.installed_app_ids()
        except Exception:
            ids = set()
        self.installed_ready.emit(ids)

    def _on_installed(self, app_ids):
        self._installed = {g.id for g in games.ALL if g.steam_app_id in app_ids}
        self._rebuild()

    def _rebuild(self):
        for row in self._rows:
            row.deleteLater()
        self._rows = []

        def order(g):
            return (g.id in self._library, g.id not in self._installed, not g.verified, g.name)

        for i, prof in enumerate(sorted(games.ALL, key=order)):
            row = GameRow(prof, prof.id in self._installed, prof.id in self._library)
            row.clicked.connect(self.game_chosen.emit)
            self.list_box.insertWidget(i, row)
            self._rows.append(row)
        self._filter(self.search.text())

    def _filter(self, text):
        q = (text or "").strip().lower()
        shown = 0
        for row in self._rows:
            hit = not q or q in row.profile.name.lower() or q in row.profile.tagline.lower()
            row.setVisible(hit)
            shown += hit
        self.empty.setVisible(shown == 0)
