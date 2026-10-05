"""The library: WorldSync's main menu.

Every game the player has added gets a card painted in that game's own
scene and colours, with a live line underneath (who's playing, who played
last). The last card adds a game. Invite codes can be pasted from here too,
since a code already says which game it's for.
"""

import webbrowser
import zlib

from PySide6.QtCore import QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (QGridLayout, QHBoxLayout, QLabel,
                               QScrollArea, QVBoxLayout, QWidget)

from .. import __version__
from . import format as fmt
from . import gamethemes, icons, scenes, theme, widgets
from .banner import WorldBanner

# Set to a Ko-fi / GitHub Sponsors URL to show the tip jar; hidden while empty.
TIP_URL = ""

CARD_W, CARD_H = 204, 124   # two columns plus a scrollbar fit the 512px window
_THUMBS: dict[tuple, object] = {}


def game_thumb(game_id: str, w: int, h: int):
    """A cached still of the game's scene, in that game's own colours."""
    key = (game_id, w, h)
    if key not in _THUMBS:
        tok = gamethemes.get(game_id).tokens()
        _THUMBS[key] = scenes.render(gamethemes.get(game_id).scene, w, h,
                                     tok["ACCENT"], tok["EMBER"], seed=zlib.crc32(game_id.encode()))
    return _THUMBS[key]


def game_font(game_id: str, px: int, bold=True) -> QFont:
    t = gamethemes.get(game_id)
    f = QFont(theme._family(t.deco))
    f.setPixelSize(px)
    f.setWeight(QFont.Bold if bold else QFont.Normal)
    if t.title_spacing:
        f.setLetterSpacing(QFont.AbsoluteSpacing, min(t.title_spacing, 2) * 0.6)
    return f


class GameCard(QWidget):
    """A game in the library, drawn as a little poster."""

    clicked = Signal(str)

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.profile = profile
        self._line = ""
        self._live = False
        self._hover = False
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setToolTip(profile.name)

    def set_line(self, text: str, live: bool = False):
        self._line, self._live = text, live
        self.update()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit(self.profile.id)

    def event(self, e):
        if e.type() in (e.Type.HoverEnter, e.Type.HoverLeave):
            self._hover = e.type() == e.Type.HoverEnter
            self.update()
        return super().event(e)

    def paintEvent(self, e):
        tok = gamethemes.get(self.profile.id).tokens()
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        clip = QPainterPath()
        clip.addRoundedRect(r, 14, 14)
        p.setClipPath(clip)
        p.drawPixmap(0, 0, game_thumb(self.profile.id, CARD_W, CARD_H))

        shade = QLinearGradient(0, CARD_H * 0.3, 0, CARD_H)
        shade.setColorAt(0, QColor(0, 0, 0, 0))
        shade.setColorAt(0.6, QColor(0, 0, 0, 150))
        shade.setColorAt(1, QColor(0, 0, 0, 225))
        p.fillRect(r, shade)
        if self._hover:
            p.fillRect(r, QColor(255, 255, 255, 14))

        # title in the game's own typeface
        p.setPen(QColor("#FFFFFF"))
        p.setFont(game_font(self.profile.id, 17))
        title_rect = QRectF(14, CARD_H - 54, CARD_W - 28, 24)
        name = self.profile.name.replace("RuneScape: ", "")
        p.drawText(title_rect, Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(name, Qt.ElideRight, int(title_rect.width())))

        # live line
        f = QFont(self.font())
        f.setPixelSize(11)
        p.setFont(f)
        x = 14
        if self._live:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(tok["ACCENT"]))
            p.drawEllipse(QRectF(x, CARD_H - 25, 7, 7))
            x += 12
        p.setPen(QColor(tok["GOLD_TEXT"]) if self._live else QColor(theme.TEXT_DIM))
        p.drawText(QRectF(x, CARD_H - 32, CARD_W - x - 12, 20), Qt.AlignLeft | Qt.AlignVCenter,
                   p.fontMetrics().elidedText(self._line, Qt.ElideRight, CARD_W - x - 12))

        if not self.profile.verified:
            p.setFont(QFont(self.font().family(), 7, QFont.Bold))
            badge = QRectF(CARD_W - 50, 10, 40, 16)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(0, 0, 0, 140))
            p.drawRoundedRect(badge, 8, 8)
            p.setPen(QColor(tok["EMBER"]))
            p.drawText(badge, Qt.AlignCenter, "BETA")

        p.setClipping(False)
        border = QColor(tok["ACCENT"]) if self._hover else QColor(255, 255, 255, 26)
        p.setPen(QPen(border, 1.6 if self._hover else 1.0))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(r, 14, 14)
        p.end()


class AddGameCard(QWidget):
    clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hover = False
        self.setFixedSize(CARD_W, CARD_H)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.clicked.emit()

    def event(self, e):
        if e.type() in (e.Type.HoverEnter, e.Type.HoverLeave):
            self._hover = e.type() == e.Type.HoverEnter
            self.update()
        return super().event(e)

    def paintEvent(self, e):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)
        p.setBrush(QColor(theme.SURFACE_2 if self._hover else theme.SURFACE))
        pen = QPen(QColor(theme.ACCENT if self._hover else theme.BORDER), 1.4, Qt.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(r, 14, 14)
        color = theme.ACCENT if self._hover else theme.TEXT_DIM
        pm = icons.pixmap("plus", color, 26)
        p.drawPixmap(int(CARD_W / 2 - 13), int(CARD_H / 2 - 26), pm)
        f = QFont(theme.display_family())
        f.setPixelSize(13)
        f.setWeight(QFont.DemiBold)
        p.setFont(f)
        p.setPen(QColor(color))
        p.drawText(QRectF(0, CARD_H / 2 + 6, CARD_W, 22), Qt.AlignCenter, "Add a game")
        p.end()


class LibraryPage(QWidget):
    game_opened = Signal(str)
    add_game_clicked = Signal()
    join_clicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: dict[str, GameCard] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # -- hero ---------------------------------------------------------------
        hero = QWidget()
        hero.setFixedHeight(150)
        self.banner = WorldBanner(150, hero)
        overlay = QWidget(hero)
        overlay.setStyleSheet("background: transparent;")
        ov = QVBoxLayout(overlay)
        ov.setContentsMargins(22, 14, 22, 14)
        ov.addStretch(1)
        brand = QHBoxLayout()
        brand.setSpacing(12)
        mark = QLabel()
        mark.setPixmap(icons.worldsync_mark(40))
        mark.setStyleSheet("background: transparent;")
        brand.addWidget(mark, 0, Qt.AlignVCenter)
        words = QVBoxLayout()
        words.setSpacing(0)
        self.wordmark = QLabel("WorldSync")
        self.wordmark.setStyleSheet("background: transparent; color: #FFFFFF;")
        self.greeting = QLabel("")
        self.greeting.setStyleSheet(f"background: transparent; color: {theme.TEXT_DIM};"
                                    "font-size: 12.5px;")
        words.addWidget(self.wordmark)
        words.addWidget(self.greeting)
        brand.addLayout(words, 1)
        ov.addLayout(brand)
        hero.resizeEvent = lambda e: (self.banner.setGeometry(0, 0, hero.width(), 150),
                                      overlay.setGeometry(0, 0, hero.width(), 150))
        root.addWidget(hero)

        # -- cards --------------------------------------------------------------
        body = QWidget()
        bb = QVBoxLayout(body)
        bb.setContentsMargins(24, 10, 24, 14)
        bb.setSpacing(10)
        self.section = QLabel("")
        self.section.setObjectName("SectionLabel")
        bb.addWidget(self.section)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        holder = QWidget()
        holder.setStyleSheet("background: transparent;")
        self.grid = QGridLayout(holder)
        self.grid.setContentsMargins(0, 2, 0, 2)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.grid.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        scroll.setWidget(holder)
        bb.addWidget(scroll, 1)

        self.add_card = AddGameCard()
        self.add_card.clicked.connect(self.add_game_clicked.emit)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        join = widgets.make_button("Join with an invite code", "ghost", "link", height=38)
        join.clicked.connect(self.join_clicked.emit)
        actions.addWidget(join, 1)
        bb.addLayout(actions)

        footer = QHBoxLayout()
        self.tip_btn = widgets.make_button("Support WorldSync", "subtle", "heart", height=26)
        self.tip_btn.setToolTip("WorldSync is free. If it saved your group a server bill, "
                                "a tip keeps it going.")
        self.tip_btn.clicked.connect(lambda: webbrowser.open(TIP_URL))
        self.tip_btn.setVisible(bool(TIP_URL))
        footer.addWidget(self.tip_btn)
        footer.addStretch(1)
        version = QLabel(f"v{__version__}  ·  free and open source")
        version.setObjectName("FooterText")
        footer.addWidget(version)
        bb.addLayout(footer)
        root.addWidget(body, 1)
        self.retheme()

    # -- public -----------------------------------------------------------------
    def retheme(self):
        self.banner.set_scene(theme.scene())
        # set through the stylesheet: the global QSS font-size would win over setFont
        self.wordmark.setStyleSheet(
            "background: transparent; color: #FFFFFF;"
            f"font-family: '{theme.display_family()}'; font-size: 30px; font-weight: 700;"
            "letter-spacing: 0.5px;")
        self.section.setText(theme.caps("Your library"))
        self.tip_btn.setIcon(icons.icon("heart", theme.EMBER, 14))

    def set_player(self, name: str, game_count: int):
        self._me = name
        hello = f"Hi {name}" if name else "Welcome"
        if game_count:
            self.greeting.setText(f"{hello}  ·  {game_count} game"
                                  f"{'s' if game_count != 1 else ''} in your library")
        else:
            self.greeting.setText(f"{hello}  ·  add your first game to get going")

    def set_games(self, profiles, world_counts: dict):
        while self.grid.count():
            item = self.grid.takeAt(0)
            w = item.widget()
            if w is not None and w is not self.add_card:
                w.deleteLater()
        self._cards = {}
        for i, prof in enumerate(profiles):
            card = GameCard(prof)
            n = world_counts.get(prof.id, 0)
            card.set_line(f"{n} world{'s' if n != 1 else ''}" if n else "No worlds yet")
            card.clicked.connect(self.game_opened.emit)
            self._cards[prof.id] = card
            self.grid.addWidget(card, i // 2, i % 2)
        i = len(profiles)
        self.grid.addWidget(self.add_card, i // 2, i % 2)

    def set_summary(self, summary: dict):
        """{game_id: {"playing": name|None, "last": (editor, iso_ts)|None, "worlds": n}}"""
        for gid, info in summary.items():
            card = self._cards.get(gid)
            if not card:
                continue
            n = info.get("worlds", 0)
            worlds = f"{n} world{'s' if n != 1 else ''}"
            if info.get("playing"):
                card.set_line(f"{info['playing']} is playing", live=True)
            elif info.get("last"):
                editor, ts = info["last"]
                editor = "you" if editor == getattr(self, "_me", None) else editor
                card.set_line(f"{worlds}  ·  {editor}, {fmt.humanize(ts)}")
            else:
                card.set_line(worlds if n else "No worlds yet")

    def sizeHint(self):
        return QSize(480, 720)
