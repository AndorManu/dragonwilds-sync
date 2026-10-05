"""Smoke tests for the real window: first run, the upgrade from 1.x, themes.

They build the actual MainWindow offscreen against a throwaway data folder
and walk the navigation, so a broken signal or a missing attribute fails CI
instead of the first person who clicks it.
"""

import json
import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QIcon  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core import paths  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    from app.ui import theme
    theme.apply(app)
    return app


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))
    data = tmp_path / "appdata"
    monkeypatch.setattr(paths, "APP_DIR", data)
    monkeypatch.setattr(paths, "CONFIG_PATH", data / "config.json")
    monkeypatch.setattr(paths, "STATE_PATH", data / "state.json")
    monkeypatch.setattr(paths, "LOG_DIR", data / "logs")
    monkeypatch.setattr(paths, "BACKUP_DIR", data / "backups")
    monkeypatch.setattr(paths, "LEGACY_CONFIG_PATH", tmp_path / "none" / "config.json")
    monkeypatch.setattr(paths, "LEGACY_STATE_PATH", tmp_path / "none" / "state.json")
    monkeypatch.setattr(paths, "LEGACY_APP_DIR", tmp_path / "DragonwildsSync")
    from app.ui import theme
    monkeypatch.setattr(theme, "UI_CACHE", data / "ui")
    return home, data


def make_window():
    from app.controller import Controller
    from app.ui.window import MainWindow
    controller = Controller()
    win = MainWindow(controller, QIcon())
    controller._poll.stop()
    return controller, win


def test_first_run_through_picker_to_a_game(qapp, sandbox):
    home, _ = sandbox
    vh = home / "AppData" / "LocalLow" / "IronGate" / "Valheim" / "worlds_local"
    vh.mkdir(parents=True)
    (vh / "Midgard.fwl").write_bytes(b"x" * 100)
    (vh / "Midgard.db").write_bytes(b"x" * 5000)

    c, win = make_window()
    from app.ui import theme
    assert win.pages.currentWidget() is win.onboarding_page
    assert theme.THEME_ID == "library"

    win.onboarding_page.name_field.edit.setText("Andor")
    win.onboarding_page._submit_name()
    assert win.pages.currentWidget() is win.addgame_page

    win.addgame_page.game_chosen.emit("valheim")
    assert theme.THEME_ID == "valheim"
    ob = win.onboarding_page
    assert ob.save_dir_field.value() == str(vh)
    assert ob.world_field.value() == "Midgard"

    shared = home / "Drive" / "Valheim - Midgard"
    ob._submit_world()
    ob.shared_field.edit.setText(str(shared))
    ob._submit_create()

    assert win.pages.currentWidget() is win.main_page
    assert c.cfg["library"] == ["valheim"]
    assert c.active_world()["game"] == "valheim"
    assert c.cfg["player_name"] == "Andor"

    win._go_library()
    assert win.pages.currentWidget() is win.library_page
    assert theme.THEME_ID == "library"
    assert list(win.library_page._cards) == ["valheim"]
    win.close()


def test_upgrade_from_dragonwilds_sync_opens_straight_into_dragonwilds(qapp, sandbox):
    _, data = sandbox
    data.mkdir(parents=True)
    (data / "config.json").write_text(json.dumps({
        "schema": 2, "player_name": "Andor", "local_save_dir": "C:/dw",
        "worlds": [{"id": "w_1", "world_name": "Ashenreach", "sync_dir": "C:/none"}],
        "active_world": "w_1",
    }))
    c, win = make_window()
    from app.ui import theme
    assert win.pages.currentWidget() is win.main_page
    assert theme.THEME_ID == "dragonwilds"
    assert c.cfg["schema"] == 3 and c.cfg["library"] == ["dragonwilds"]
    assert (data / "config.v2.bak").exists()
    # the Dragonwilds-only extras are offered here...
    assert win.main_page._has_characters
    win.close()


def test_secret_stays_shut_outside_dragonwilds(qapp, sandbox):
    _, data = sandbox
    data.mkdir(parents=True)
    (data / "config.json").write_text(json.dumps({
        "schema": 3, "player_name": "Andor", "library": ["raft"], "last_view": "raft",
        "worlds": [{"id": "w_1", "game": "raft", "world_name": "Sea", "sync_dir": "C:/none"}],
        "active_world": "w_1",
    }))
    c, win = make_window()
    assert win.pages.currentWidget() is win.main_page
    assert not win.main_page._has_characters
    win._awaken_secret()
    assert win.pages.currentWidget() is win.main_page
    win.close()


def test_every_theme_applies_and_every_scene_paints(qapp):
    from app.ui import gamethemes, scenes, theme
    for tid in gamethemes.THEMES:
        theme.apply_game(tid)
        assert theme.THEME_ID == tid
        pm = scenes.render(gamethemes.get(tid).scene, 160, 60, theme.ACCENT, theme.EMBER)
        assert not pm.isNull()
    theme.apply_game("dragonwilds")
