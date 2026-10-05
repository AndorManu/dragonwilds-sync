"""Render the app's key screens to PNG for the README - no window flashing.

Run:  .venv\\Scripts\\python.exe tools\\screenshots.py
Writes docs/screenshots/*.png from a throwaway home folder and config in a
temp directory (the real per-user data is never touched). Every name and
world here is made up.
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Redirect storage and the "home" folder BEFORE anything reads them.
scratch = Path(tempfile.mkdtemp(prefix="worldsync_shots_"))
home = scratch / "home"
os.environ["USERPROFILE"] = str(home)
os.environ["LOCALAPPDATA"] = str(home / "AppData" / "Local")
os.environ["APPDATA"] = str(home / "AppData" / "Roaming")

from app.core import paths  # noqa: E402

paths.APP_DIR = scratch / "appdata"
paths.CONFIG_PATH = paths.APP_DIR / "config.json"
paths.STATE_PATH = paths.APP_DIR / "state.json"
paths.LOG_DIR = paths.APP_DIR / "logs"
paths.BACKUP_DIR = paths.APP_DIR / "backups"
paths.LEGACY_CONFIG_PATH = scratch / "nolegacy" / "config.json"
paths.LEGACY_STATE_PATH = scratch / "nolegacy" / "state.json"
paths.LEGACY_APP_DIR = scratch / "nolegacy"

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.core import config, games, presence, steam, storage, telemetry  # noqa: E402

telemetry.ENDPOINT = ""   # screenshots must never send reports
from app.core.logs import setup_logging  # noqa: E402
from app.core.sync import _backup_files  # noqa: E402
from app.controller import Controller  # noqa: E402
from app.ui import theme  # noqa: E402
from app.ui.window import MainWindow  # noqa: E402

theme.UI_CACHE = paths.APP_DIR / "ui"
OUT = ROOT / "docs" / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)
SHOTS: dict[str, QPixmap] = {}


def ts(hours_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def write(path: Path, data: bytes = b"x" * 4096):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def shoot(window, name):
    QTest.qWait(350)
    pm = window.grab()
    pm.save(str(OUT / f"{name}.png"))
    SHOTS[name] = pm
    print("  wrote", name + ".png")


def clear_toasts(window):
    host = window.toasts
    for toast in list(host.findChildren(QWidget)):
        if toast.parent() is host:
            host._box.removeWidget(toast)
            toast.deleteLater()
    host.hide()
    QTest.qWait(50)


# -- a believable group across four games ------------------------------------------

PEOPLE = [("Reinier", "🪓", None), ("Bram", "🛡️", None), ("Elise", "🏹", "#5EA2EF"),
          ("Kim", "🌙", "#B78AF7"), ("Andor", "🐉", None)]

NOTES = {
    "valheim": ["Found a crypt full of surtling cores", "Moved the portal hub to the plains",
                "Elder down. Swamp next week?", "Built the longhouse roof, finally"],
    "v_rising": ["Castle walls up, servants are hunting", "Took down Grayson the Armourer",
                 "Night run to the Silverlight hills", "Coffins for everyone"],
    "dragonwilds": ["Built the gatehouse, found the swamp cave", "Tamed the salamander. It has opinions.",
                    "Runecrafting at 30!", "Cleared the old mine"],
    "palworld": ["Base moved next to the ore field", "Caught a shiny Lamball", "Automated the berry farm",
                 "Breeding farm is running"],
    "seven_days_to_die": ["Survived horde night 14", "Spike trench around the base",
                          "Looted the shotgun messiah factory", "Forge and workbench upgraded"],
    "core_keeper": ["Opened the Azeos wilderness", "Automated the copper drills",
                    "Ghorm the Devourer is down", "Fishing pond and a kitchen"],
}


def history_for(game_id: str):
    out = []
    for i, (name, emoji, color) in enumerate(PEOPLE[1:]):
        entry = {"version": 10 + i, "editor": name, "timestamp": ts(70 - i * 22 + 2),
                 "duration_s": 3600 + i * 1700, "emoji": emoji,
                 "note": NOTES[game_id][i % len(NOTES[game_id])]}
        if color:
            entry["color"] = color
        out.append(entry)
    return out


def seed():
    drive = home / "Google Drive" / "WorldSync"
    worlds = []
    cfg, _ = config.migrate_config({})
    cfg.update({"player_name": "Andor", "player_emoji": "🐉"})

    def add(game_id, world_id, label, save_root, files):
        profile = games.get(game_id)
        for rel in files:
            write(save_root / rel)
        shared = drive / f"{profile.short} - {label or world_id}"
        shared.mkdir(parents=True, exist_ok=True)
        for rel in files:
            write(shared / rel)
        hist = history_for(game_id)
        storage.write_json(shared / paths.MANIFEST_NAME, {
            "version": hist[-1]["version"], "last_editor": hist[-1]["editor"],
            "timestamp": hist[-1]["timestamp"], "world_name": world_id,
            "history": hist, "app_schema": 1, "game": game_id})
        world = config.make_world(world_id, str(shared), game=game_id, label=label,
                                  share_link="https://drive.google.com/drive/folders/x")
        worlds.append(world)
        config.add_to_library(cfg, game_id)
        if game_id != "dragonwilds":
            config.set_game_save_dir(cfg, game_id, str(save_root))
        return world, shared

    lowlow = home / "AppData" / "LocalLow"
    v, v_shared = add("valheim", "Midgard", None, lowlow / "IronGate" / "Valheim" / "worlds_local",
                      ["Midgard.fwl", "Midgard.db"])
    r, r_shared = add("v_rising", "4b5e8f9c-1d2e", "Dunley Nights",
                      lowlow / "Stunlock Studios" / "VRising" / "Saves" / "v3",
                      ["4b5e8f9c-1d2e/AutoSave_31.save.gz"])
    dw_root = home / "AppData" / "Local" / "RSDragonwilds" / "Saved" / "SaveGames"
    d, d_shared = add("dragonwilds", "Ashenreach", None, dw_root,
                      ["Ashenreach.sav", "Ashenreach.sav.backup"])
    cfg["local_save_dir"] = str(dw_root)
    p, p_shared = add("palworld", "9F3A6C0D2B7E4A1C8D5F0E6B3A9C7D21", "Palpagos Crew",
                      home / "AppData" / "Local" / "Pal" / "Saved" / "SaveGames" / "765611",
                      ["9F3A6C0D2B7E4A1C8D5F0E6B3A9C7D21/Level.sav"])
    s, s_shared = add("seven_days_to_die", "Pregen06k1/Horde Night", "Horde Night",
                      home / "AppData" / "Roaming" / "7DaysToDie",
                      ["Saves/Pregen06k1/Horde Night/main.ttw"])
    k, k_shared = add("core_keeper", "1", "Slot 2",
                      lowlow / "Pugstorm" / "Core Keeper" / "Steam" / "765611",
                      ["worlds/1.world.gzip"])
    cfg["worlds"] = worlds
    cfg["active_world"] = v["id"]
    cfg["last_view"] = "library"
    state = {"schema": 3, "worlds": {}}
    for w in worlds:
        manifest = storage.read_json(Path(w["sync_dir"]) / paths.MANIFEST_NAME)
        state["worlds"][w["id"]] = {"last_applied_version": manifest["version"], "last_hash": "x"}
    storage.save_config(cfg)
    storage.save_state(state)
    return {"valheim": (v, v_shared), "v_rising": (r, r_shared), "dragonwilds": (d, d_shared),
            "palworld": (p, p_shared), "seven_days_to_die": (s, s_shared),
            "core_keeper": (k, k_shared)}


def collage(names, out_name, cols=3, scale=0.62):
    pms = [SHOTS[n] for n in names]
    w, h = int(pms[0].width() * scale), int(pms[0].height() * scale)
    rows = (len(pms) + cols - 1) // cols
    gap = 18
    sheet = QPixmap(cols * w + (cols + 1) * gap, rows * h + (rows + 1) * gap)
    sheet.fill(QColor("#07090E"))
    p = QPainter(sheet)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    for i, pm in enumerate(pms):
        x = gap + (i % cols) * (w + gap)
        y = gap + (i // cols) * (h + gap)
        p.drawPixmap(x, y, pm.scaled(w, h, Qt.KeepAspectRatio, Qt.SmoothTransformation))
    p.end()
    sheet.save(str(OUT / f"{out_name}.png"))
    print("  wrote", out_name + ".png")


def main():
    setup_logging()
    app = QApplication(sys.argv)
    theme.apply(app)
    steam.installed_app_ids = lambda libraries=None: {"892970", "1604030", "1623730", "1374490"}

    # ---- first run -------------------------------------------------------------------
    write(home / "AppData" / "LocalLow" / "IronGate" / "Valheim" / "worlds_local" / "Midgard.fwl")
    write(home / "AppData" / "LocalLow" / "IronGate" / "Valheim" / "worlds_local" / "Midgard.db",
          b"x" * 60000)
    c0 = Controller()
    w0 = MainWindow(c0, QIcon())
    w0.setAttribute(Qt.WA_DontShowOnScreen, True)
    w0.show()
    shoot(w0, "01_welcome")
    w0.onboarding_page.name_field.edit.setText("Andor")
    w0.onboarding_page._submit_name()
    QTest.qWait(400)
    shoot(w0, "02_pick_a_game")
    w0.addgame_page.game_chosen.emit("valheim")
    w0.onboarding_page._go(3)
    shoot(w0, "03_find_the_world")
    w0._really_quit = True
    w0.close()

    # ---- a full library -------------------------------------------------------------------
    seeded = seed()
    presence.start_playing(seeded["v_rising"][1], "Kim", "🌙")
    c = Controller()
    c._poll.stop()
    win = MainWindow(c, QIcon())
    win.setAttribute(Qt.WA_DontShowOnScreen, True)
    win.show()
    QTest.qWait(900)       # library summary thread
    shoot(win, "04_library")

    order = ["valheim", "v_rising", "dragonwilds", "palworld", "seven_days_to_die", "core_keeper"]
    for gid in order:
        world, shared = seeded[gid]
        win._open_game(gid)
        QTest.qWait(200)
        win.main_page.set_status(c._world_status(world))
        clear_toasts(win)
        shoot(win, f"game_{gid}")
    collage([f"game_{g}" for g in order], "05_every_game_its_own_look")

    # live states
    win._open_game("v_rising")
    win.main_page.set_status(c._world_status(seeded["v_rising"][0]))
    shoot(win, "06_friend_playing")
    presence.stop_playing(seeded["v_rising"][1], "Kim")

    win._open_game("valheim")
    world, shared = seeded["valheim"]
    win.main_page.set_status(c._world_status(world))
    win.main_page.set_phase("ingame")
    shoot(win, "07_in_game")
    win.main_page.set_phase("idle")

    win._open_invite()
    win.invite_page._generate()
    shoot(win, "08_invite")
    win._show_page(win.main_page)

    ov = win.confirm
    ov.title_label.setText("Overwrite your local progress?")
    ov.body_label.setText(
        "Your local save has changed since your last sync, but a newer save "
        "(v13, from Kim) is waiting in the shared folder.\n\n"
        "Continuing will replace your local, un-shared progress.")
    ov.danger_btn.setText("Overwrite")
    ov.safe_btn.setText("Keep my progress")
    ov.setGeometry(win.chrome.rect())
    ov.show()
    ov.raise_()
    shoot(win, "09_conflict")
    ov.hide()

    flat = config.effective_cfg(c.cfg, world)
    root = config.backup_root_for(world["id"])
    files = sorted(Path(flat["local_save_dir"]).glob("Midgard*"))
    _backup_files(files, "local_v12", root)
    _backup_files(files, "shared_v13", root)
    from app.core import backups as bk
    bk.create_checkpoint(flat["local_save_dir"], "Midgard", "Before Moder", root,
                         patterns=flat["patterns"])
    win._open_backups()
    shoot(win, "10_backups")

    win._show_page(win.about_page)
    shoot(win, "11_about")

    # drop the per-game singles; the collage carries them
    for gid in order:
        (OUT / f"game_{gid}.png").unlink(missing_ok=True)
    win._really_quit = True
    win.close()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
