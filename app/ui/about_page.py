"""About: version, a short changelog, and one quiet credit."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QScrollArea, QVBoxLayout, QWidget

from .. import __version__
from . import icons, theme, widgets

CHANGELOG = [
    ("1.2.0", [
        "A whole new look — a fantasy game-launcher, world-art and all",
        "Update the app in one click, straight from the shared folder",
        "“Test my setup” checks everything's wired up right",
        "Name and keep checkpoints; restore any of them",
        "Pass the turn to a friend with a tray ping",
        "Won't share a corrupt or half-synced save — the group stays safe",
        "Optional phone-checkable status page in the shared folder",
    ]),
    ("1.1.0", [
        "Invite codes — friends join a world by pasting one code",
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
        mark.setPixmap(icons.mark_pixmap(44))
        mark.setAlignment(Qt.AlignHCenter)
        root.addWidget(mark)
        root.addSpacing(10)

        name = QLabel("Dragonwilds Sync")
        name.setAlignment(Qt.AlignHCenter)
        name.setStyleSheet(
            f"font-family: '{theme.deco_family()}'; font-size: 24px; font-weight: 700;"
            f"color: {theme.GOLD_TEXT}; letter-spacing: 1px;")
        root.addWidget(name)

        ver = QLabel(f"Version {__version__}")
        ver.setAlignment(Qt.AlignHCenter)
        ver.setStyleSheet(f"color: {theme.TEXT_DIM}; font-size: 12px;")
        root.addWidget(ver)
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
