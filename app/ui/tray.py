"""System tray: keep watch while the window sleeps."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

log = logging.getLogger("dwsync.tray")


class TrayManager(QObject):
    open_requested = Signal()
    quit_requested = Signal()
    tip_clicked = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(parent)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tip_shown = False
        self._last_message = None
        if not self.available:
            log.info("No system tray available")
            return

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("WorldSync")

        menu = QMenu()
        open_action = menu.addAction("Open WorldSync")
        open_action.triggered.connect(self.open_requested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.messageClicked.connect(self._on_message_clicked)
        self.tray.show()

    def _on_message_clicked(self):
        if self._last_message == "tip":
            self.tip_clicked.emit()
        else:
            self.open_requested.emit()

    def _show(self, kind, title, body, ms):
        self._last_message = kind
        self.tray.showMessage(title, body, QSystemTrayIcon.Information, ms)

    def notify_tip(self, shares: int):
        if self.available:
            self._show("tip", "Enjoying WorldSync? ☕",
                       f"Your group has shared {shares} sessions without renting a server. "
                       f"WorldSync is free; click here if you'd like to buy me a coffee.", 10000)

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_requested.emit()

    def notify_friend_push(self, world_name: str, editor: str, version: int):
        if self.available:
            self._show("open", f"Your turn in {world_name}?",
                       f"{editor} shared v{version} - the newest save is waiting for you.", 8000)

    def notify_nudge(self, from_player: str, world_name: str):
        if self.available:
            self._show("open", f"It's your turn in {world_name}",
                       f"{from_player} passed you the world - jump in when you're ready.", 8000)

    def notify_update(self, version: str):
        if self.available:
            self._show("open", "Update available",
                       f"Version {version} is ready. Open WorldSync to update.", 7000)

    def show_minimized_tip(self):
        if self.available and not self._tip_shown:
            self._tip_shown = True
            self._show("open", "Still keeping watch",
                       "WorldSync lives in the tray now - you'll get a ping "
                       "when a friend shares a save. Right-click the icon to quit.", 6000)
