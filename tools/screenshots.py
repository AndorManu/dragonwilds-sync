"""Render every app state to PNG for design review — no window flashing.

Run:  .venv\\Scripts\\python.exe tools\\screenshots.py
Writes docs/screenshots/*.png using a throwaway config in a temp folder
(the real per-user config is never touched).
"""

import json
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
from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QWidget  # noqa: E402

from app.core import config, presence, storage, sync  # noqa: E402
from app.core.logs import setup_logging  # noqa: E402
from app.core.sync import _backup_files  # noqa: E402
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
        {"version": 11, "editor": "Reinier", "timestamp": ts(76),
         "duration_s": 5400, "emoji": "🪓"},
        {"version": 12, "editor": "Bram", "timestamp": ts(29),
         "note": "Tamed the salamander. It has opinions.", "duration_s": 8100,
         "character": "Grimjaw",
         "portrait": "male_A_01|SkinTone3|Preset2|Color2|M_B_Preset2|Color1"},
        {"version": 13, "editor": "Andor", "timestamp": ts(7),
         "note": "Built the gatehouse, found the swamp cave", "duration_s": 4520,
         "character": "Negrito",
         "portrait": "male_A_01|SkinTone1|Preset7|Color8|M_D_Preset4|Color2"},
        {"version": 14, "editor": "Elise", "timestamp": ts(1.8), "duration_s": 6300,
         "character": "Sylwen", "color": "#5EA2EF",
         "portrait": "female_A_01|SkinTone6|Preset11|Color5|F_PresetNone|Color3"},
    ]
    storage.write_json(shared / paths.MANIFEST_NAME, {
        "version": 14, "last_editor": "Elise", "timestamp": ts(1.8),
        "world_name": WORLD, "history": history, "app_schema": 1,
    })
    world = config.make_world(WORLD, str(shared),
                              share_link="https://drive.google.com/drive/folders/x")
    world2 = config.make_world("Frostspire", str(scratch / "shared2"))
    cfg, _ = config.migrate_config({})
    cfg.update({
        "player_name": "Andor", "player_emoji": "🐉",
        "local_save_dir": str(save_dir),
        "active_world": world["id"],
        "worlds": [world, world2],
    })
    return cfg, world, shared, save_dir


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

    # ---- onboarding states (no config yet) --------------------------------------
    controller = Controller()
    window = MainWindow(controller, QIcon())
    window.setAttribute(Qt.WA_DontShowOnScreen, True)  # render fully, never flash
    window.show()
    shoot(window, "01_onboarding_welcome")
    window.onboarding_page._go(1)
    shoot(window, "02_onboarding_name")
    window.onboarding_page._go(2)
    shoot(window, "03_onboarding_choice")
    window.onboarding_page._go(4)
    shoot(window, "04_onboarding_shared")
    window.onboarding_page.code_field.edit.setText("DWS1.demo")
    window.onboarding_page._join_info = {
        # deliberately non-existent folder so the watcher keeps spinning
        "world_name": "Emberfall", "folder_name": "Emberfall Sync",
        "share_link": "https://drive.google.com/drive/folders/x"}
    window.onboarding_page._start_watching()
    window.onboarding_page._go(6)
    shoot(window, "05_onboarding_join_watch")
    window.onboarding_page._watch_timer.stop()
    window.close()

    # ---- configured states -----------------------------------------------------------
    cfg, world, shared, save_dir = seed_world()
    storage.save_config(cfg)
    storage.save_state({"schema": 2, "worlds": {
        world["id"]: {"last_applied_version": 14, "last_hash": "x"}}})

    controller2 = Controller()
    window2 = MainWindow(controller2, QIcon())
    window2.setAttribute(Qt.WA_DontShowOnScreen, True)
    window2.show()

    window2.main_page.set_status(controller2._world_status(world))
    shoot(window2, "06_main_up_to_date")

    config.world_state(controller2.state, world["id"])["last_applied_version"] = 13
    window2.main_page.set_status(controller2._world_status(world))
    shoot(window2, "07_main_new_save")

    presence.start_playing(shared, "Bram", "🪓")
    window2.main_page.set_status(controller2._world_status(world))
    shoot(window2, "08_main_friend_playing")
    presence.stop_playing(shared, "Bram")

    presence.claim_next(shared, "Elise", "🏹")
    config.world_state(controller2.state, world["id"])["last_applied_version"] = 14
    window2.main_page.set_status(controller2._world_status(world))
    shoot(window2, "09_main_turn_claimed")
    presence.clear_next(shared)

    window2.main_page.set_status(controller2._world_status(world))
    window2.main_page.set_phase("ingame")
    shoot(window2, "10_main_in_game")
    window2.main_page.set_phase("idle")

    window2.toasts.show_toast("success",
                              "Shared your progress as v15 — your friends are up to date.")
    QTest.qWait(400)
    shoot(window2, "11_main_toast")
    clear_toasts(window2)

    # invite page
    window2.invite_page.load(world)
    window2._show_page(window2.invite_page)
    window2.invite_page._generate()
    shoot(window2, "12_invite")

    # backups page
    files = sorted(save_dir.glob(f"{WORLD}*"))
    root = config.backup_root_for(world["id"])
    _backup_files(files, "local_v13", root)
    _backup_files(files, "shared_v14", root)
    window2._open_backups()
    shoot(window2, "13_backups")

    # settings + about
    window2.settings_page.load(cfg, world)
    window2._show_page(window2.settings_page)
    shoot(window2, "14_settings")
    window2._show_page(window2.about_page)
    shoot(window2, "15_about")
    window2._show_page(window2.main_page)

    # note overlay
    window2.note_overlay.open(world["id"], 15)
    shoot(window2, "16_note_prompt")
    window2.note_overlay._skip()

    # preflight page
    from app.core import preflight
    window2._show_page(window2.preflight_page)
    window2.preflight_page.show_results(preflight.run(cfg, world))
    shoot(window2, "18_preflight")

    # backups with a checkpoint
    from app.core.sync import _backup_files as _bk
    root = config.backup_root_for(world["id"])
    from app.core import backups as bkmod
    bkmod.create_checkpoint(save_dir, WORLD, "Before the dragon", root)
    window2._reload_backups()
    window2._show_page(window2.backups_page)
    shoot(window2, "19_backups_checkpoints")

    # update bar on the main screen
    window2._show_page(window2.main_page)
    window2.main_page.set_status(controller2._world_status(world))
    window2.main_page.show_update_bar("1.3.0", "Bram")
    QTest.qWait(150)
    shoot(window2, "20_update_bar")
    window2.main_page.hide_update_bar()

    # characters page (synthetic characters in the scratch dir)
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "tests"))
    from test_characters import make_character
    chars_dir = scratch / "SaveCharacters"
    make_character(chars_dir, "Negrito")
    make_character(chars_dir, "Minblyat")
    controller2.cfg["characters_dir"] = str(chars_dir)

    # give Negrito a believable real-item bag so the demo reads naturally
    from app.core import items as _items
    _sample = _items.search(min_rank=0)
    _picks = {}
    for _r in _sample:                       # a spread across rarities
        _picks.setdefault(_r["rank"], _r)
    _neg = chars_dir / "Negrito.json"
    _data = json.loads(_neg.read_text(encoding="utf-8"))
    _inv = {"MaxSlotIndex": 30}
    for _i, _row in enumerate(list(_picks.values()) * 3):
        _slot = {"GUID": f"g{_i}", "ItemData": _row["id"]}
        if _row["max"] > 1:
            _slot["Count"] = min(_row["max"], (_i + 1) * 7)
        else:
            _slot["Durability"] = 300 + _i * 90
        _inv[str(_i)] = _slot
    _data["GameProgress"]["Inventory"] = _inv
    _neg.write_text(json.dumps(_data, indent="\t"), encoding="utf-8")
    window2._open_characters()
    shoot(window2, "21_characters")

    # the grimoire (opened the way anyone opens it: through the eye)
    window2._open_grimoire()
    shoot(window2, "22_grimoire")
    window2.grimoire_page.char_combo.setCurrentText("Negrito")
    QTest.qWait(60)
    window2.grimoire_page._switch_tab(1)
    _cells = list(window2.grimoire_page._bag_cells.values())
    if _cells:
        window2.grimoire_page._select_slot(_cells[min(4, len(_cells) - 1)])
    shoot(window2, "22b_grimoire_bag")
    window2.grimoire_page._switch_tab(2)   # mirror
    shoot(window2, "22e_grimoire_mirror")
    window2.grimoire_page._switch_tab(3)   # scrolls
    shoot(window2, "22c_grimoire_scrolls")
    window2.grimoire_page._switch_tab(0)

    # the conjuring catalogue
    from app.ui.item_picker import ItemPicker
    picker = ItemPicker(window2)
    picker.setAttribute(Qt.WA_DontShowOnScreen, True)
    picker.show()
    picker.search.setText("dragon")
    QTest.qWait(120)
    if picker.list.count():
        picker.list.setCurrentRow(0)
    QTest.qWait(120)
    picker.grab().save(str(OUT / "22d_conjure.png"))
    print("  wrote 22d_conjure.png")
    picker.close()

    # the saga
    from app.core import saga as saga_mod
    saga_mod.bump_stats(shared, "Andor", 4520)
    saga_mod.bump_stats(shared, "Elise", 6300)
    saga_mod.bump_stats(shared, "Bram", 8100)
    saga_mod.bump_stats(shared, "Bram", 5400)
    window2._open_saga()
    shoot(window2, "23_saga")

    # conflict overlay
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
    shoot(window2, "17_conflict")
    ov.hide()

    window2._really_quit = True
    window2.close()
    print("done ->", OUT)


if __name__ == "__main__":
    main()
