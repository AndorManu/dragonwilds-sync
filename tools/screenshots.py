"""Render every app state to PNG for design review — no window flashing.

Run:  .venv\\Scripts\\python.exe tools\\screenshots.py
Writes docs/screenshots/*.png using a throwaway config in a temp folder
(the real per-user config is never touched).
"""

import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Redirect all app storage into a scratch folder BEFORE anything reads it.
scratch = Path(tempfile.mkdtemp(prefix="dwsync_shots_"))
from app.core import paths  # noqa: E402

paths.APP_DIR = scratch / "appdata"
paths.CONFIG_PATH = paths.APP_DIR / "config.json"
paths.STATE_PATH = paths.APP_DIR / "state.json"
paths.LOG_DIR = paths.APP_DIR / "logs"
paths.BACKUP_DIR = paths.APP_DIR / "backups"
paths.LEGACY_CONFIG_PATH = scratch / "nolegacy" / "config.json"
paths.LEGACY_STATE_PATH = scratch / "nolegacy" / "state.json"

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.core import storage, sync  # noqa: E402
from app.core.logs import setup_logging  # noqa: E402
from app.controller import Controller  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.window import MainWindow  # noqa: E402

theme.UI_CACHE = paths.APP_DIR / "ui"

OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

WORLD = "Minhalla"


def ts(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def seed_world():
    save_dir = scratch / "saves"
    shared = scratch / "shared"
    save_dir.mkdir(exist_ok=True)
    shared.mkdir(exist_ok=True)
    (save_dir / f"{WORLD}.sav").write_bytes(b"save-data")
    (save_dir / f"{WORLD}.sav.backup").write_bytes(b"save-data-backup")
    (shared / f"{WORLD}.sav").write_bytes(b"shared-save")
    (shared / f"{WORLD}.sav.backup").write_bytes(b"shared-save-backup")
    history = [
        {"version": 11, "editor": "Reinier", "timestamp": ts(76)},
        {"version": 12, "editor": "Bram", "timestamp": ts(29)},
        {"version": 13, "editor": "Andor", "timestamp": ts(7)},
        {"version": 14, "editor": "Elise", "timestamp": ts(1.8)},
    ]
    storage.write_json(shared / paths.MANIFEST_NAME, {
        "version": 14, "last_editor": "Elise", "timestamp": ts(1.8),
        "world_name": WORLD, "history": history,
    })
    cfg = {
        "player_name": "Andor",
        "local_save_dir": str(save_dir),
        "world_name": WORLD,
        "sync_dir": str(shared),
        "exe_path": None,
        "steam_app_id": "1374490",
    }
    return cfg


def shoot(window, name):
    QTest.qWait(300)
    window.grab().save(str(OUT / f"{name}.png"))
    print("  wrote", name + ".png")


def clear_toasts(window):
    host = window.toasts
    for toast in list(host.findChildren(QWidget)):
        if toast.parent() is host:
            host._box.removeWidget(toast)
            toast.deleteLater()
    host.hide()
    QTest.qWait(50)


def main():
    setup_logging()
    app = QApplication(sys.argv)
    theme.apply(app)

    # ---- onboarding states (no config yet) ---------------------------------
    controller = Controller()
    window = MainWindow(controller)
    window.setAttribute(Qt.WA_DontShowOnScreen, True)  # render fully, never flash
    window.show()
    shoot(window, "1_onboarding_welcome")
    window.onboarding_page._go(1)
    shoot(window, "2_onboarding_name")
    window.onboarding_page._go(3)
    shoot(window, "3_onboarding_shared")
    window.close()

    # ---- configured states ---------------------------------------------------
    cfg = seed_world()
    storage.save_config(cfg)

    state_uptodate = {"last_applied_version": 14, "last_hash": "x"}
    storage.save_state(state_uptodate)
    controller2 = Controller()
    window2 = MainWindow(controller2)
    window2.setAttribute(Qt.WA_DontShowOnScreen, True)
    window2.show()
    window2.main_page.set_status(sync.get_status(cfg, state_uptodate))
    shoot(window2, "4_main_up_to_date")

    state_behind = {"last_applied_version": 13, "last_hash": "x"}
    window2.main_page.set_status(sync.get_status(cfg, state_behind))
    shoot(window2, "5_main_new_save")

    window2.main_page.set_phase("ingame")
    shoot(window2, "6_main_in_game")
    window2.main_page.set_phase("idle")

    window2.toasts.show_toast("success", "Shared your progress as v15 — your friends are up to date.")
    QTest.qWait(400)
    shoot(window2, "7_main_toast")
    clear_toasts(window2)

    window2.settings_page.load(cfg)
    window2._show_page(window2.settings_page)
    shoot(window2, "8_settings")
    window2._show_page(window2.main_page)

    # Conflict overlay (rendered without blocking).
    ov = window2.confirm
    ov.title_label.setText("Overwrite your local progress?")
    ov.body_label.setText(
        "Your local save has changed since your last sync, but a newer save "
        "(v14, from Elise) is waiting in the shared folder.\n\n"
        "Continuing will replace your local, un-shared progress.")
    ov.danger_btn.setText("Overwrite")
    ov.safe_btn.setText("Keep my progress")
    ov.setGeometry(window2.chrome.rect())
    ov.show()
    ov.raise_()
    shoot(window2, "9_conflict")
    ov.hide()

    print("done ->", OUT)


if __name__ == "__main__":
    main()
