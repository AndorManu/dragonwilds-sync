"""WorldSync multi-game engine: profiles, discovery, folder worlds, safety."""

import json
import os
import time
from pathlib import Path

import pytest

from app.core import backups, config, games, health, invite, steam, worldhistory
from app.core.sync import (SyncResult, do_pull, do_push, world_files,
                           world_fingerprint)


def touch(path: Path, data: bytes = b"x" * 2048, mtime: float | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    if mtime:
        os.utime(path, (mtime, mtime))
    return path


def logs():
    out = []
    return out, out.append


def yes(title, body):
    return True


def no(title, body):
    return False


# ---------------------------------------------------------------------------
# profiles
# ---------------------------------------------------------------------------

def test_every_profile_is_complete():
    ids = set()
    for g in games.ALL:
        assert g.id not in ids
        ids.add(g.id)
        assert g.name and g.steam_app_id.isdigit()
        assert g.process_names and all(n.lower().endswith(".exe") for n in g.process_names)
        assert g.save_roots and g.discover
        assert g.tagline
        for t in g.save_roots:
            assert t.startswith("{"), "save roots must be anchored to a known folder"
    assert len(games.ALL) == 10


def test_only_dragonwilds_uses_the_legacy_rule():
    legacy = [g.id for g in games.ALL if g.patterns is None]
    assert legacy == ["dragonwilds"]


def test_unknown_game_falls_back_to_dragonwilds():
    assert games.get("nope") is games.DRAGONWILDS
    assert games.get(None) is games.DRAGONWILDS


def test_expand_picks_newest_wildcard_folder(tmp_path):
    old = tmp_path / "Pal" / "Saved" / "SaveGames" / "111"
    new = tmp_path / "Pal" / "Saved" / "SaveGames" / "222"
    old.mkdir(parents=True)
    new.mkdir(parents=True)
    os.utime(old, (time.time() - 1000, time.time() - 1000))
    tokens = {"LOCALAPPDATA": str(tmp_path)}
    assert games.expand("{LOCALAPPDATA}/Pal/Saved/SaveGames/*", tokens) == new


def test_expand_missing_returns_none(tmp_path):
    assert games.expand("{LOCALLOW}/Nope/*/x", {"LOCALLOW": str(tmp_path)}) is None


def test_world_id_validation():
    assert games.is_valid_world_id("Navezgane/My Save")
    assert games.is_valid_world_id("3ad85aea")
    for bad in ("", " x", "../evil", "a/../b", "C:/x", "a//b"):
        assert not games.is_valid_world_id(bad)


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------

def test_discover_valheim_both_layouts(tmp_path):
    now = time.time()
    touch(tmp_path / "Old.fwl", mtime=now - 500)
    touch(tmp_path / "Old.db", mtime=now - 500)
    touch(tmp_path / "Midgard" / "Midgard.db", mtime=now)
    found = games.discover_worlds(games.VALHEIM, tmp_path)
    assert [w.id for w in found] == ["Midgard", "Old"]


def test_discover_seven_days_map_and_save(tmp_path):
    touch(tmp_path / "Saves" / "Navezgane" / "Alpha" / "main.ttw")
    touch(tmp_path / "Saves" / "Pregen06k1" / "Beta" / "main.ttw")
    found = {w.id: w for w in games.discover_worlds(games.SEVEN_DAYS, tmp_path)}
    assert set(found) == {"Navezgane/Alpha", "Pregen06k1/Beta"}
    assert found["Navezgane/Alpha"].label == "Navezgane / Alpha"


def test_discover_core_keeper_slots(tmp_path):
    touch(tmp_path / "worlds" / "0.world.gzip")
    touch(tmp_path / "worlds" / "2.world.gzip")
    labels = {w.id: w.label for w in games.discover_worlds(games.CORE_KEEPER, tmp_path)}
    assert labels == {"0": "Slot 1", "2": "Slot 3"}


def test_discover_v_rising_reads_world_name(tmp_path):
    guid = "4b5e8f9c-aaaa"
    touch(tmp_path / guid / "AutoSave_12.save.gz")
    (tmp_path / guid / "ServerHostSettings.json").write_text(
        json.dumps({"Name": "Castle Night"}), encoding="utf-8")
    [w] = games.discover_worlds(games.V_RISING, tmp_path)
    assert (w.id, w.label) == (guid, "Castle Night")


def test_discover_missing_folder_is_empty(tmp_path):
    assert games.discover_worlds(games.RAFT, tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# folder worlds through the sync core
# ---------------------------------------------------------------------------

def flat_for(profile, save_dir, sync_dir, world, player="Andor"):
    return {
        "player_name": player, "local_save_dir": str(save_dir),
        "world_name": world, "sync_dir": str(sync_dir), "exe_path": None,
        "game": profile.id, "mirror": profile.mirror,
        "patterns": list(profile.patterns) if profile.patterns is not None else None,
    }


@pytest.fixture
def vr(tmp_path):
    a, b, shared = tmp_path / "a", tmp_path / "b", tmp_path / "shared"
    for p in (a, b, shared):
        p.mkdir()
    world = "guid-1"
    return a, b, shared, world


def test_folder_world_roundtrip_with_nested_files(vr, tmp_path):
    a, b, shared, world = vr
    touch(a / world / "AutoSave_1.save.gz", b"one" * 500)
    touch(a / world / "ServerGameSettings.json", b"{}" * 600)
    touch(a / "other-world" / "AutoSave_9.save.gz")    # must not travel
    sa, sb = {"last_applied_version": 0, "last_hash": None}, \
             {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    res, _ = do_push(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")
    assert res == SyncResult.PUSHED
    assert (shared / world / "AutoSave_1.save.gz").exists()
    assert not (shared / "other-world").exists()
    assert json.loads((shared / "version.json").read_text())["game"] == "v_rising"

    res, _ = do_pull(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, yes, tmp_path / "bk")
    assert res == SyncResult.PULLED
    assert (b / world / "AutoSave_1.save.gz").read_bytes() == b"one" * 500


def test_mirror_removes_rotated_autosaves(vr, tmp_path):
    a, b, shared, world = vr
    touch(a / world / "AutoSave_1.save.gz")
    sa = {"last_applied_version": 0, "last_hash": None}
    sb = {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    do_push(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")
    do_pull(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, yes, tmp_path / "bk")

    # Kim plays: the game rotates autosave 1 out and writes autosave 2
    (b / world / "AutoSave_1.save.gz").unlink()
    touch(b / world / "AutoSave_2.save.gz")
    do_push(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, yes, tmp_path / "bk")
    assert not (shared / world / "AutoSave_1.save.gz").exists()

    do_pull(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")
    assert sorted(p.name for p in (a / world).iterdir()) == ["AutoSave_2.save.gz"]


def test_new_autosave_counts_as_local_change(vr, tmp_path):
    """A folder world's fingerprint covers every file, not just the first."""
    a, b, shared, world = vr
    touch(a / world / "AutoSave_1.save.gz")
    sa = {"last_applied_version": 0, "last_hash": None}
    sb = {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    do_push(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")
    do_pull(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, yes, tmp_path / "bk")

    touch(b / world / "AutoSave_2.save.gz")                       # Kim played offline
    touch(a / world / "AutoSave_3.save.gz")                       # Andor shared meanwhile
    do_push(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")

    res, _ = do_pull(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, no, tmp_path / "bk")
    assert res == SyncResult.CONFLICT_CANCELLED


def test_conflict_backup_keeps_folder_structure(vr, tmp_path):
    a, b, shared, world = vr
    touch(a / world / "AutoSave_1.save.gz", b"A" * 3000)
    sa = {"last_applied_version": 0, "last_hash": None}
    sb = {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    touch(b / world / "AutoSave_7.save.gz", b"B" * 3000)          # Kim's own copy
    do_push(flat_for(games.V_RISING, a, shared, world), sa, log, yes, tmp_path / "bk")
    do_pull(flat_for(games.V_RISING, b, shared, world, "Kim"), sb, log, yes, tmp_path / "bk")
    backed = list((tmp_path / "bk").rglob("AutoSave_7.save.gz"))
    assert backed and backed[0].parent.name == world


def test_seven_days_carries_map_and_save(tmp_path):
    a, shared = tmp_path / "a", tmp_path / "shared"
    touch(a / "Saves" / "Pregen06k1" / "Alpha" / "main.ttw")
    touch(a / "Saves" / "Pregen06k1" / "Alpha" / "Player" / "76561.ttp")
    touch(a / "GeneratedWorlds" / "Pregen06k1" / "dtm.raw")
    touch(a / "GeneratedWorlds" / "OtherMap" / "dtm.raw")
    files = world_files(a, "Pregen06k1/Alpha", list(games.SEVEN_DAYS.patterns))
    rels = sorted(f.relative_to(a).as_posix() for f in files)
    assert rels == ["GeneratedWorlds/Pregen06k1/dtm.raw",
                    "Saves/Pregen06k1/Alpha/Player/76561.ttp",
                    "Saves/Pregen06k1/Alpha/main.ttw"]
    state = {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    res, _ = do_push(flat_for(games.SEVEN_DAYS, a, shared, "Pregen06k1/Alpha"),
                     state, log, yes, tmp_path / "bk")
    assert res == SyncResult.PUSHED
    assert (shared / "GeneratedWorlds" / "Pregen06k1" / "dtm.raw").exists()


def test_prefix_patterns_dont_catch_similar_names(tmp_path):
    touch(tmp_path / "Test.fwl")
    touch(tmp_path / "Test.db")
    touch(tmp_path / "Test2.fwl")
    touch(tmp_path / "Test2.db")
    names = [f.name for f in world_files(tmp_path, "Test", list(games.VALHEIM.patterns))]
    assert names == ["Test.db", "Test.fwl"]


def test_world_names_with_glob_characters_are_literal(tmp_path):
    touch(tmp_path / "[A]" / "x.sav")
    touch(tmp_path / "A" / "y.sav")
    files = world_files(tmp_path, "[A]", ["{world}/**/*"])
    assert [f.name for f in files] == ["x.sav"]


def test_legacy_fingerprint_is_first_file_hash(tmp_path):
    from app.core.sync import sha256_file
    f1 = touch(tmp_path / "W.sav", b"abc")
    touch(tmp_path / "W.sav.backup", b"def")
    files = world_files(tmp_path, "W")
    assert world_fingerprint(files, tmp_path, None) == sha256_file(f1)


# ---------------------------------------------------------------------------
# the wrong-game guard
# ---------------------------------------------------------------------------

def test_pull_refuses_other_games_world(tmp_path):
    a, shared = tmp_path / "a", tmp_path / "shared"
    touch(a / "Midgard.fwl")
    touch(a / "Midgard.db")
    _, log = logs()
    s1 = {"last_applied_version": 0, "last_hash": None}
    do_push(flat_for(games.VALHEIM, a, shared, "Midgard"), s1, log, yes, tmp_path / "bk")
    b = tmp_path / "b"
    b.mkdir()
    s2 = {"last_applied_version": 0, "last_hash": None}
    res, _ = do_pull(flat_for(games.RAFT, b, shared, "Midgard"), s2, log, yes, tmp_path / "bk")
    assert res == SyncResult.WRONG_GAME
    assert not any(b.iterdir())


def test_old_manifest_counts_as_dragonwilds(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    (shared / "version.json").write_text(json.dumps({"version": 3, "world_name": "W"}))
    a = tmp_path / "a"
    touch(a / "W" / "x.dat")
    _, log = logs()
    state = {"last_applied_version": 0, "last_hash": None}
    res, _ = do_push(flat_for(games.RAFT, a, shared, "W"), state, log, yes, tmp_path / "bk")
    assert res == SyncResult.WRONG_GAME
    dw = flat_for(games.DRAGONWILDS, tmp_path / "dw", shared, "W")
    res, _ = do_pull(dw, {"last_applied_version": 0, "last_hash": None}, log, yes, tmp_path / "bk")
    assert res != SyncResult.WRONG_GAME


def test_dragonwilds_push_still_stamps_game(tmp_path):
    a, shared = tmp_path / "a", tmp_path / "shared"
    touch(a / "W.sav")
    _, log = logs()
    do_push(flat_for(games.DRAGONWILDS, a, shared, "W"),
            {"last_applied_version": 0, "last_hash": None}, log, yes, tmp_path / "bk")
    assert json.loads((shared / "version.json").read_text())["game"] == "dragonwilds"


# ---------------------------------------------------------------------------
# health, backups, group history for folder worlds
# ---------------------------------------------------------------------------

def test_health_uses_biggest_file_for_folder_worlds(tmp_path):
    pats = list(games.VALHEIM.patterns)
    touch(tmp_path / "M.fwl", b"x" * 80)          # tiny metadata file
    touch(tmp_path / "M.db", b"x" * 50_000)
    assert health.check_local_save(tmp_path, "M", pats).ok
    (tmp_path / "M.db").write_bytes(b"")
    assert not health.check_local_save(tmp_path, "M", pats).ok


def test_still_syncing_sees_nested_partial_files(tmp_path):
    pats = ["{world}/**/*"]
    touch(tmp_path / "W" / "AutoSave_1.save.gz")
    assert not health.shared_still_syncing(tmp_path, "W", pats)
    touch(tmp_path / "W" / "AutoSave_2.save.gz.tmp")
    assert health.shared_still_syncing(tmp_path, "W", pats)


def test_checkpoint_and_mirror_restore_folder_world(tmp_path):
    pats = ["{world}/**/*"]
    save, root = tmp_path / "save", tmp_path / "bk"
    touch(save / "W" / "AutoSave_1.save.gz", b"before" * 400)
    cp = backups.create_checkpoint(save, "W", "Before boss", root, patterns=pats)
    assert cp.file_count == 1
    assert (cp.path / "W" / "AutoSave_1.save.gz").exists()

    touch(save / "W" / "AutoSave_2.save.gz", b"after" * 400)
    (save / "W" / "AutoSave_1.save.gz").write_bytes(b"changed" * 400)
    n = backups.restore_backup(cp.path, save, "W", root, patterns=pats, mirror=True)
    assert n == 1
    assert sorted(p.name for p in (save / "W").iterdir()) == ["AutoSave_1.save.gz"]
    assert (save / "W" / "AutoSave_1.save.gz").read_bytes() == b"before" * 400
    pre = [b for b in backups.list_backups(root) if b.label == "pre_restore"]
    assert pre and pre[0].file_count == 2


def test_group_history_archives_nested_world(tmp_path):
    pats = ["{world}/**/*"]
    touch(tmp_path / "W" / "a" / "b.dat")
    assert worldhistory.archive_version(tmp_path, "W", 4, patterns=pats)
    [v] = worldhistory.list_versions(tmp_path)
    assert v.file_count == 1 and (v.path / "W" / "a" / "b.dat").exists()


# ---------------------------------------------------------------------------
# config v3
# ---------------------------------------------------------------------------

def test_v2_config_migrates_to_library():
    v2 = {"schema": 2, "player_name": "Andor", "local_save_dir": "C:/dw",
          "worlds": [{"id": "w_1", "world_name": "Ash", "sync_dir": "S"}],
          "active_world": "w_1"}
    v3, _ = config.migrate_config(v2)
    assert v3["schema"] == 3
    assert v3["library"] == ["dragonwilds"]
    assert v3["worlds"][0]["game"] == "dragonwilds"
    assert v3["last_view"] == "dragonwilds"
    assert config.game_save_dir(v3, "dragonwilds") == "C:/dw"


def test_effective_cfg_for_folder_game():
    cfg, _ = config.migrate_config({"player_name": "Andor", "worlds": []})
    config.set_game_save_dir(cfg, "valheim", "D:/vh")
    world = config.make_world("Midgard", "S", game="valheim")
    flat = config.effective_cfg(cfg, world)
    assert flat["local_save_dir"] == "D:/vh"
    assert flat["patterns"] == list(games.VALHEIM.patterns)
    assert flat["mirror"] is True
    assert flat["steam_app_id"] == "892970"
    assert flat["process_names"] == ["valheim.exe"]
    # Dragonwilds' save folder is untouched by other games' settings
    assert config.game_save_dir(cfg, "dragonwilds") != "D:/vh"


def test_remove_game_only_when_empty():
    cfg, _ = config.migrate_config({"player_name": "A", "worlds": []})
    config.add_to_library(cfg, "raft")
    cfg["worlds"].append(config.make_world("Sea", "S", game="raft"))
    with pytest.raises(ValueError):
        config.remove_from_library(cfg, "raft")
    cfg["worlds"] = []
    config.remove_from_library(cfg, "raft")
    assert "raft" not in cfg["library"]


# ---------------------------------------------------------------------------
# invites and Steam detection
# ---------------------------------------------------------------------------

def test_invite_carries_game():
    code = invite.encode("Midgard", "Valheim crew", None, game="valheim")
    assert code.startswith("WS1.")
    assert invite.decode(code)["game"] == "valheim"


def test_dragonwilds_invites_stay_readable_by_1x():
    code = invite.encode("Ash", "DW crew", None)
    assert code.startswith("DWS1.")
    assert invite.decode(code)["game"] == "dragonwilds"


def test_steam_install_detection(tmp_path):
    lib = tmp_path / "SteamLibrary"
    apps = lib / "steamapps"
    apps.mkdir(parents=True)
    (apps / "appmanifest_892970.acf").write_text(
        '"AppState"\n{\n\t"appid"\t"892970"\n\t"installdir"\t"Valheim"\n}\n')
    touch(apps / "common" / "Valheim" / "valheim.exe")
    touch(apps / "common" / "Valheim" / "tools" / "valheim.exe")
    assert steam.installed_app_ids([lib]) == {"892970"}
    exe = steam.find_game_exe(games.VALHEIM, libraries=[lib])
    assert exe == apps / "common" / "Valheim" / "valheim.exe"
    assert steam.find_game_exe(games.RAFT, libraries=[lib]) is None


def test_empty_world_name_matches_nothing(tmp_path):
    touch(tmp_path / "W" / "x.dat")
    assert world_files(tmp_path, "", ["{world}/**/*"]) == []
