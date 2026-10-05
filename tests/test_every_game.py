"""End to end, for every supported game, on two simulated PCs.

Each game gets its real save-folder layout (Steam-ID folders and all) under
a fake home folder. The test then runs what a group actually does: find the
save folder, discover the world, share it from PC A, pull it on PC B, play
on B, share back, pull on A, and hit a real conflict. Other worlds sitting
in the same save folder must never travel or be touched.
"""

import json
from pathlib import Path

import pytest

from app.core import config, games, health
from app.core.sync import SyncResult, do_pull, do_push
from tools.games_doc import render as render_games_doc

STEAM = "76561198000000001"

# game id -> (save folder under home, world id, the world's files, other files there)
LAYOUTS = {
    "dragonwilds": (
        "AppData/Local/RSDragonwilds/Saved/SaveGames", "Ashenreach",
        ["Ashenreach.sav", "Ashenreach.sav.backup"],
        ["Frostspire.sav"]),
    "valheim": (
        "AppData/LocalLow/IronGate/Valheim/worlds_local", "Midgard",
        ["Midgard.fwl", "Midgard.db", "Midgard.db.old"],
        ["Midgard2.fwl", "Midgard2.db"]),
    "enshrouded": (
        "Saved Games/Enshrouded", "3ad85aea",
        ["3ad85aea", "3ad85aea-1", "3ad85aea_info"],
        ["9b1c2d3e", "characters"]),
    "palworld": (
        f"AppData/Local/Pal/Saved/SaveGames/{STEAM}", "0123456789ABCDEF0123456789ABCDEF",
        ["0123456789ABCDEF0123456789ABCDEF/Level.sav",
         "0123456789ABCDEF0123456789ABCDEF/LevelMeta.sav",
         "0123456789ABCDEF0123456789ABCDEF/Players/00000000000000000000000000000001.sav"],
        ["FEDCBA9876543210FEDCBA9876543210/Level.sav"]),
    "core_keeper": (
        f"AppData/LocalLow/Pugstorm/Core Keeper/Steam/{STEAM}", "1",
        ["worlds/1.world.gzip", "maps/0/1.mapparts.gzip", "worldinfos/1.json",
         "worldgenparams/1.json"],
        ["worlds/0.world.gzip", "maps/0/0.mapparts.gzip", "worldinfos/0.json",
         "worlds/10.world.gzip"]),
    "sons_of_the_forest": (
        f"AppData/LocalLow/Endnight/SonsOfTheForest/Saves/{STEAM}/Multiplayer", "0412345678",
        ["0412345678/GameStateSaveData.json", "0412345678/SaveData.json",
         "0412345678/PlayerInventorySaveData.json"],
        ["0499999999/SaveData.json"]),
    "v_rising": (
        "AppData/LocalLow/Stunlock Studios/VRising/Saves/v3", "a1b2c3d4-0000",
        ["a1b2c3d4-0000/AutoSave_31.save.gz", "a1b2c3d4-0000/ServerHostSettings.json",
         "a1b2c3d4-0000/ServerGameSettings.json"],
        ["ffff0000-1111/AutoSave_2.save.gz"]),
    "grounded": (
        "Saved Games/Grounded/2535412345678901", "Backyard",
        ["Backyard/SaveData.sav", "Backyard/Screenshot.png"],
        ["Hedge/SaveData.sav"]),
    "raft": (
        f"AppData/LocalLow/Redbeet Interactive/Raft/User/User_{STEAM}/World", "Seagull",
        ["Seagull/Seagull.rgd", "Seagull/Seagull-Latest.rgd"],
        ["Island/Island.rgd"]),
    "seven_days_to_die": (
        "AppData/Roaming/7DaysToDie", "Pregen06k1/Horde Night",
        ["Saves/Pregen06k1/Horde Night/main.ttw",
         "Saves/Pregen06k1/Horde Night/Player/76561198000000001.ttp",
         "GeneratedWorlds/Pregen06k1/dtm.raw"],
        ["Saves/Navezgane/Other/main.ttw", "GeneratedWorlds/OtherMap/dtm.raw"]),
}


def test_every_game_has_a_layout_here():
    assert set(LAYOUTS) == {g.id for g in games.ALL}


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((text * 300).encode())       # comfortably over the health minimum


def use_home(monkeypatch, home: Path):
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("LOCALAPPDATA", str(home / "AppData" / "Local"))
    monkeypatch.setenv("APPDATA", str(home / "AppData" / "Roaming"))


def snapshot(root: Path, rels) -> dict:
    return {r: (root / r).read_bytes() for r in rels}


def make_pc(monkeypatch, home: Path, game_id: str, shared: Path, player: str):
    use_home(monkeypatch, home)
    profile = games.get(game_id)
    save_dir = games.default_save_dir(profile)
    assert save_dir is not None, f"{game_id}: save folder not found from its templates"
    cfg, _ = config.migrate_config({"player_name": player, "worlds": []})
    config.set_game_save_dir(cfg, game_id, str(save_dir))
    world = config.make_world(LAYOUTS[game_id][1], str(shared), game=game_id)
    return config.effective_cfg(cfg, world), save_dir


def logs():
    return lambda message: None


def yes(title, body):
    return True


def no(title, body):
    return False


@pytest.mark.parametrize("game_id", sorted(LAYOUTS))
def test_full_round_trip(game_id, tmp_path, monkeypatch):
    rel_root, world_id, world_files, others = LAYOUTS[game_id]
    shared = tmp_path / "cloud" / "shared"
    home_a, home_b = tmp_path / "pc_a", tmp_path / "pc_b"
    for rel in world_files:
        write(home_a / rel_root / rel, f"A-{rel}")
    for rel in others:
        write(home_a / rel_root / rel, f"A-other-{rel}")
        write(home_b / rel_root / rel, f"B-other-{rel}")       # B has its own other worlds

    # PC A finds the folder and the world, then shares it
    flat_a, root_a = make_pc(monkeypatch, home_a, game_id, shared, "Andor")
    assert root_a == home_a / rel_root
    found = [w.id for w in games.discover_worlds(games.get(game_id), root_a)]
    assert world_id in found
    assert health.check_local_save(root_a, world_id, flat_a["patterns"]).ok
    state_a = {"last_applied_version": 0, "last_hash": None}
    res, _ = do_push(flat_a, state_a, logs(), yes, tmp_path / "bk_a")
    assert res == SyncResult.PUSHED
    manifest = json.loads((shared / "version.json").read_text())
    assert manifest["game"] == game_id
    for rel in world_files:
        assert (shared / rel).is_file(), f"{game_id}: {rel} didn't travel"
    for rel in others:
        assert not (shared / rel).exists(), f"{game_id}: {rel} leaked into the shared folder"

    # PC B pulls it next to its own worlds
    flat_b, root_b = make_pc(monkeypatch, home_b, game_id, shared, "Kim")
    others_b = snapshot(root_b, others)
    state_b = {"last_applied_version": 0, "last_hash": None}
    res, _ = do_pull(flat_b, state_b, logs(), yes, tmp_path / "bk_b")
    assert res == SyncResult.PULLED
    assert snapshot(root_b, world_files) == snapshot(root_a, world_files)
    assert snapshot(root_b, others) == others_b

    # Kim plays: the main file changes (and folder worlds grow a new autosave)
    write(root_b / world_files[0], "B-played")
    extra = None
    if flat_b["patterns"] is not None and "/" in world_files[0]:
        extra = str(Path(world_files[0]).parent / "AutoSave_new.dat").replace("\\", "/")
        write(root_b / extra, "B-new-autosave")
        from app.core.sync import world_files as files_of
        belongs = {f.relative_to(root_b).as_posix()
                   for f in files_of(root_b, world_id, flat_b["patterns"])}
        if extra not in belongs:      # slot-file games: a stray file isn't the world's
            extra = None
    res, _ = do_push(flat_b, state_b, logs(), yes, tmp_path / "bk_b")
    assert res == SyncResult.PUSHED

    # Andor picks it up
    use_home(monkeypatch, home_a)
    res, _ = do_pull(flat_a, state_a, logs(), yes, tmp_path / "bk_a")
    assert res == SyncResult.PULLED
    assert (root_a / world_files[0]).read_bytes() == (root_b / world_files[0]).read_bytes()
    if extra:
        assert (root_a / extra).read_bytes() == (root_b / extra).read_bytes()
    for rel in others:
        assert (root_a / rel).read_bytes().startswith(b"A-other-")

    # a real conflict: Andor played offline while Kim shared again
    write(root_a / world_files[0], "A-offline")
    write(root_b / world_files[0], "B-second-session")
    use_home(monkeypatch, home_b)
    assert do_push(flat_b, state_b, logs(), yes, tmp_path / "bk_b")[0] == SyncResult.PUSHED
    use_home(monkeypatch, home_a)
    res, _ = do_pull(flat_a, state_a, logs(), no, tmp_path / "bk_a")
    assert res == SyncResult.CONFLICT_CANCELLED
    assert (root_a / world_files[0]).read_bytes().startswith(b"A-offline")


def test_every_game_has_a_setup_guide():
    for g in games.ALL:
        steps = games.setup_steps(g)
        assert len(steps) >= 3, f"{g.id} needs a real setup guide"
        assert all("—" not in s for s in steps)     # no em dashes in user-facing text
    assert len(games.COMMON_STEPS) >= 3


def test_games_doc_is_up_to_date():
    doc = Path(__file__).resolve().parent.parent / "docs" / "GAMES.md"
    assert doc.read_text(encoding="utf-8") == render_games_doc(), \
        "docs/GAMES.md is stale - run tools/games_doc.py"
