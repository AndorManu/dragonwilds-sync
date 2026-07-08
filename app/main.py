"""Application entry point."""

import ctypes
import sys
from pathlib import Path

from PySide6.QtCore import QLockFile
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from . import APP_NAME
from .controller import Controller
from .core import paths
from .core.logs import setup_logging
from .ui import theme
from .ui.window import MainWindow


def resource_path(relative: str) -> Path:
    """Works from source and from inside the PyInstaller bundle."""
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    return base / relative


def main():
    log = setup_logging()
    log.info("---- %s starting ----", APP_NAME)

    if sys.platform == "win32":
        # Give the process its own taskbar identity (icon grouping, pinning).
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DragonwildsSync.App")

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    icon_file = resource_path("app/assets/icon.ico")
    if icon_file.exists():
        app.setWindowIcon(QIcon(str(icon_file)))

    paths.APP_DIR.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(paths.APP_DIR / "app.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(1):
        QMessageBox.information(None, APP_NAME,
                                "Dragonwilds Sync is already running — check your taskbar.")
        return 0

    theme.apply(app)
    controller = Controller()
    window = MainWindow(controller)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
