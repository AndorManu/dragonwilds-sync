"""Config schema v2 migration and accessors."""

from app.core import config


V1_CFG = {
    "player_name": "Andor",
    "local_save_dir": r"C:\saves",
    "world_name": "Minhalla",
    "sync_dir": r"G:\My Drive\Dragonwilds Sync",
    "exe_path": None,
    "steam_app_id": "1374490",
}


def test_v1_config_migrates_to_one_world():
    v2, wid = config.migrate_config(dict(V1_CFG))
    assert v2["schema"] == 2
    assert v2["player_name"] == "Andor"
    assert v2["local_save_dir"] == r"C:\saves"
    assert len(v2["worlds"]) == 1
    world = v2["worlds"][0]
    assert world["id"] == wid
    assert world["world_name"] == "Minhalla"
    assert world["sync_dir"] == r"G:\My Drive\Dragonwilds Sync"
    assert v2["active_world"] == wid


def test_v2_config_passes_through_and_backfills_defaults():
    v2, wid = config.migrate_config(dict(V1_CFG))
    again, wid2 = config.migrate_config(v2)
    assert wid2 is None
    assert again["worlds"] == v2["worlds"]
    assert "close_to_tray" in again  # defaults backfilled


def test_v1_state_migrates_under_world_id():
    state = {"last_applied_version": 7, "last_hash": "abc"}
    v2 = config.migrate_state(state, "w_test")
    assert v2["worlds"]["w_test"]["last_applied_version"] == 7
    assert v2["worlds"]["w_test"]["last_hash"] == "abc"
    # idempotent
    assert config.migrate_state(v2, "w_test") is v2


def test_effective_cfg_matches_v1_shape():
    v2, wid = config.migrate_config(dict(V1_CFG))
    flat = config.effective_cfg(v2, config.active_world(v2))
    assert flat == V1_CFG


def test_world_state_slice_is_mutable_and_persistent():
    state = {"schema": 2, "worlds": {}}
    slot = config.world_state(state, "w_x")
    assert slot["last_applied_version"] == 0
    slot["last_applied_version"] = 5
    assert state["worlds"]["w_x"]["last_applied_version"] == 5
    assert config.world_state(state, "w_x") is slot


def test_active_world_falls_back_to_first():
    v2, _ = config.migrate_config(dict(V1_CFG))
    v2["active_world"] = "w_gone"
    assert config.active_world(v2)["world_name"] == "Minhalla"


def test_make_world_ids_unique():
    a = config.make_world("A", "x")
    b = config.make_world("A", "x")
    assert a["id"] != b["id"]
