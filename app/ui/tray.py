"""System tray: keep watch while the window sleeps."""

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

log = logging.getLogger("dwsync.tray")


class TrayManager(QObject):
    open_requested = Signal()
    quit_requested = Signal()

    def __init__(self, icon: QIcon, parent=None):
        super().__init__(parent)
        self.available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tip_shown = False
        if not self.available:
            log.info("No system tray available")
            return

        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("Dragonwilds Sync")

        menu = QMenu()
        open_action = menu.addAction("Open Dragonwilds Sync")
        open_action.triggered.connect(self.open_requested.emit)
        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)
        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_activated)
        self.tray.messageClicked.connect(self.open_requested.emit)
        self.tray.show()

    def _on_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.open_requested.emit()

    def notify_friend_push(self, world_name: str, editor: str, version: int):
        if self.available:
            self.tray.showMessage(
                f"Your turn in {world_name}?",
                f"{editor} shared v{version} — the wilds await.",
                QSystemTrayIcon.Information, 8000)

    def show_minimized_tip(self):
        if self.available and not self._tip_shown:
            self._tip_shown = True
            self.tray.showMessage(
                "Still keeping watch",
                "Dragonwilds Sync lives in the tray now — you'll get a ping "
                "when a friend shares a save. Right-click the icon to quit.",
                QSystemTrayIcon.Information, 6000)
