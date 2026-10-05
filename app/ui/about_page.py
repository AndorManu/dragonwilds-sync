"""About: version, a short changelog, and one quiet credit."""

import webbrowser

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .. import __version__
from ..core import games
from . import icons, theme, widgets
from .library_page import TIP_URL

CHANGELOG = [
    ("2.0.0", [
        "Dragonwilds Sync is now WorldSync: one app for every co-op world",
        "Ten games to start: Dragonwilds, Valheim, Enshrouded, Palworld, Core Keeper, "
        "Sons of the Forest, V Rising, Grounded, Raft and 7 Days to Die",
        "A game library as the new home screen, with a picker that puts your "
        "installed Steam games first",
        "Every game has its own look, from Valheim's aurora to V Rising's blood moon",
        "A step-by-step setup guide for every game (world menu → How to set up)",
        "Finds each game's save folder and lists its worlds by when you last played",
        "Folder-based worlds sync whole, including rotated autosaves",
        "Refuses to copy one game's world into another",
        "Your Dragonwilds worlds, settings and invite codes carry straight over",
    ]),
    ("1.3.2", [
        "Small cleanup: wording, version info and screenshots brought up to date",
    ]),
    ("1.3.1", [
        "First public release, open source under MIT",
        "Every release is now built automatically from the public source",
    ]),
    ("1.3.0", [
        "Characters! Portraits in the feed, playtime, per-session vault backups",
        "A character can travel with you between your own PCs",
        "The Saga - the fellowship's totals and an exportable chronicle",
        "Group history: the last three world versions kept in the shared folder",
        "See who a friend is playing as, live and in the feed",
        "Per-world banner colors, a soft chime on Play, Discord Rich Presence",
        "…and the dragon's eye keeps a secret for the curious",
    ]),
    ("1.2.0", [
        "A whole new look - a fantasy game-launcher, world-art and all",
        "Update the app in one click, straight from the shared folder",
        "“Test my setup” checks everything's wired up right",
        "Name and keep checkpoints; restore any of them",
        "Pass the turn to a friend with a tray ping",
        "Won't share a corrupt or half-synced save - the group stays safe",
        "Optional phone-checkable status page in the shared folder",
    ]),
    ("1.1.0", [
        "Invite codes - friends join a world by pasting one code",
        "Multiple worlds with a quick switcher",
        "Live presence: see when a friend is mid-session before you play",
        "Runs in the tray; pings you when it's your turn",
        "Webhook notifications (Discord / Slack / ntfy)",
        "Backup browser with one-click restore",
        "Session notes and session lengths in the feed",
        "Finds your game install automatically",
    ]),
    ("1.0.0", [
        "First release: pull → play → share, with versioning and "
        "conflict protection in both directions",
    ]),
]


class AboutPage(QWidget):
    back_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        root = QVBoxLayout(self)
        root.setContentsMargins(28, 4, 28, 20)
        root.setSpacing(0)

        header = QHBoxLayout()
        back = widgets.icon_button("chevron-left", theme.TEXT_DIM, tooltip="Back")
        back.clicked.connect(self.back_requested.emit)
        header.addWidget(back)
        title = QLabel("About")
        title.setStyleSheet("font-size: 18px; font-weight: 650;")
        header.addSpacing(6)
        header.addWidget(title)
        header.addStretch(1)
        root.addLayout(header)
        root.addSpacing(18)

        mark = QLabel()
        mark.setPixmap(icons.worldsync_mark(48))
        mark.setAlignment(Qt.AlignHCenter)
        root.addWidget(mark)
        root.addSpacing(10)

        name = QLabel("WorldSync")
        name.setAlignment(Qt.AlignHCenter)
        name.setStyleSheet(
            f"font-family: '{theme.deco_family()}'; font-size: 24px; font-weight: 700;"
            f"color: {theme.GOLD_TEXT}; letter-spacing: 1px;")
        root.addWidget(name)

        ver = QLabel(f"Version {__version__}  ·  {len(games.ALL)} games  ·  free and open source")
        ver.setAlignment(Qt.AlignHCenter)
        ver.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        root.addWidget(ver)
        if TIP_URL:
            root.addSpacing(10)
            tip = widgets.make_button("Buy me a coffee", "ghost", "heart", height=32)
            tip.setToolTip("WorldSync stays free. Tips keep new games coming.")
            tip.clicked.connect(lambda: webbrowser.open(TIP_URL))
            root.addWidget(tip, 0, Qt.AlignHCenter)
        root.addSpacing(16)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        body.setStyleSheet("background: transparent;")
        box = QVBoxLayout(body)
        box.setContentsMargins(2, 2, 10, 2)
        box.setSpacing(8)

        for version, entries in CHANGELOG:
            head = QLabel(f"V{version}")
            head.setObjectName("SectionLabel")
            box.addWidget(head)
            for entry in entries:
                line = QLabel(f"·  {entry}")
                line.setWordWrap(True)
                line.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12.5px;")
                box.addWidget(line)
            box.addSpacing(8)
        box.addStretch(1)
        scroll.setWidget(body)
        root.addWidget(scroll, 1)

        credit = QLabel("Forged by MrNothing")
        credit.setAlignment(Qt.AlignHCenter)
        credit.setStyleSheet(f"color: {theme.TEXT_FAINT}; font-size: 11px;"
                             f"letter-spacing: 1px;")
        root.addSpacing(10)
        root.addWidget(credit)
