"""Tests for the core sync protocol: push / pull / version bump / conflicts.

These pin down the behavior that was already validated in the prototype, plus
the two additions (push-side stale check, safety backups).
"""

import json
from pathlib import Path

import pytest

from app.core import paths
from app.core.sync import SyncResult, do_pull, do_push, get_status, sha256_file

WORLD = "Minhalla"


@pytest.fixture
def env(tmp_path):
    """A local save folder, a shared folder, a backup root, and a fresh config/state."""
    save_dir = tmp_path / "local_saves"
    sync_dir = tmp_path / "shared"
    backups = tmp_path / "backups"
    save_dir.mkdir()
    sync_dir.mkdir()
    cfg = {
        "player_name": "Andor",
        "local_save_dir": str(save_dir),
        "world_name": WORLD,
        "sync_dir": str(sync_dir),
        "exe_path": None,
    }
    state = {"last_applied_version": 0, "last_hash": None}
    return cfg, state, save_dir, sync_dir, backups


def write_save(folder: Path, content: str):
    (folder / f"{WORLD}.sav").write_bytes(content.encode())
    (folder / f"{WORLD}.sav.backup").write_bytes((content + "-backup").encode())


def read_manifest(sync_dir: Path):
    return json.loads((sync_dir / paths.MANIFEST_NAME).read_text())


def logs():
    messages = []
    return messages, messages.append


def confirm_yes(title, body):
    return True


def confirm_no(title, body):
    return False


# ---------------------------------------------------------------------------
# push
# ---------------------------------------------------------------------------

def test_first_push_creates_manifest_v1(env):
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "session-1")

    _, log = logs()
    result, state = do_push(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PUSHED
    manifest = read_manifest(sync_dir)
    assert manifest["version"] == 1
    assert manifest["last_editor"] == "Andor"
    assert manifest["world_name"] == WORLD
    assert len(manifest["history"]) == 1
    assert (sync_dir / f"{WORLD}.sav").exists()
    assert (sync_dir / f"{WORLD}.sav.backup").exists()
    assert state["last_applied_version"] == 1
    assert state["last_hash"] == sha256_file(save_dir / f"{WORLD}.sav")


def test_push_bumps_version_and_appends_history(env):
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "session-1")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)

    write_save(save_dir, "session-2")
    result, state = do_push(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PUSHED
    manifest = read_manifest(sync_dir)
    assert manifest["version"] == 2
    assert [e["version"] for e in manifest["history"]] == [1, 2]
    assert (sync_dir / f"{WORLD}.sav").read_bytes() == b"session-2"


def test_push_with_no_local_files(env):
    cfg, state, save_dir, sync_dir, backups = env
    _, log = logs()
    result, state = do_push(cfg, state, log, confirm_yes, backups)
    assert result == SyncResult.NOTHING_TO_PUSH
    assert not (sync_dir / paths.MANIFEST_NAME).exists()
    assert state["last_applied_version"] == 0


def test_push_stale_cancelled_when_friend_pushed_meanwhile(env):
    """Someone pushed while we were playing; declining keeps their save intact."""
    cfg, state, save_dir, sync_dir, backups = env
    # Friend's newer session lands in the shared folder (v1), we never pulled it.
    push_as_friend(env, "friend-session")

    _, log = logs()
    write_save(save_dir, "my-offline-session")
    result, state = do_push(cfg, state, log, confirm_no, backups)

    assert result == SyncResult.STALE_CANCELLED
    assert read_manifest(sync_dir)["version"] == 1
    assert (sync_dir / f"{WORLD}.sav").read_bytes() == b"friend-session"
    assert state["last_applied_version"] == 0


def test_push_stale_accepted_overwrites_and_backs_up(env):
    cfg, state, save_dir, sync_dir, backups = env
    push_as_friend(env, "friend-session")

    _, log = logs()
    write_save(save_dir, "my-offline-session")
    result, state = do_push(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PUSHED
    manifest = read_manifest(sync_dir)
    assert manifest["version"] == 2
    assert manifest["last_editor"] == "Andor"
    assert (sync_dir / f"{WORLD}.sav").read_bytes() == b"my-offline-session"
    # The friend's overwritten session was backed up locally.
    backup_folders = list(backups.iterdir())
    assert len(backup_folders) == 1
    assert (backup_folders[0] / f"{WORLD}.sav").read_bytes() == b"friend-session"


def test_push_version_survives_deleted_manifest(env):
    """If the manifest vanishes/corrupts, the version never goes backwards."""
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "session-1")
    _, log = logs()
    for content in ("session-1", "session-2", "session-3"):
        write_save(save_dir, content)
        _, state = do_push(cfg, state, log, confirm_yes, backups)
    assert state["last_applied_version"] == 3

    (sync_dir / paths.MANIFEST_NAME).unlink()
    write_save(save_dir, "session-4")
    result, state = do_push(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PUSHED
    assert read_manifest(sync_dir)["version"] == 4


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

def push_as_friend(env, content="friend-session", name="Bram"):
    cfg, _, _, sync_dir, backups = env
    staging = sync_dir.parent / f"staging_{name}"
    staging.mkdir(exist_ok=True)
    write_save(staging, content)
    friend_cfg = dict(cfg, player_name=name, local_save_dir=str(staging))
    friend_state = {"last_applied_version": 0, "last_hash": None}
    _, log = logs()
    do_push(friend_cfg, friend_state, log, confirm_yes, backups)


def test_pull_with_no_manifest(env):
    cfg, state, *_ , backups = env
    _, log = logs()
    result, state = do_pull(cfg, state, log, confirm_yes, backups)
    assert result == SyncResult.NO_SHARED
    assert state["last_applied_version"] == 0


def test_pull_applies_newer_save(env):
    cfg, state, save_dir, sync_dir, backups = env
    push_as_friend(env, "friend-session")

    _, log = logs()
    result, state = do_pull(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PULLED
    assert (save_dir / f"{WORLD}.sav").read_bytes() == b"friend-session"
    assert (save_dir / f"{WORLD}.sav.backup").exists()
    assert state["last_applied_version"] == 1
    assert state["last_hash"] == sha256_file(save_dir / f"{WORLD}.sav")


def test_pull_skips_when_up_to_date(env):
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "mine")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)

    result, state = do_pull(cfg, state, log, confirm_yes, backups)
    assert result == SyncResult.UP_TO_DATE
    assert (save_dir / f"{WORLD}.sav").read_bytes() == b"mine"


def test_pull_conflict_cancelled_keeps_local_files(env):
    """Local save changed without a push + newer shared save → decline keeps ours."""
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "synced-point")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)  # v1, hash recorded

    push_as_friend(env, "friend-newer")            # shared moves to v2
    write_save(save_dir, "played-offline")         # local diverges from last_hash

    result, state = do_pull(cfg, state, log, confirm_no, backups)

    assert result == SyncResult.CONFLICT_CANCELLED
    assert (save_dir / f"{WORLD}.sav").read_bytes() == b"played-offline"
    assert state["last_applied_version"] == 1


def test_pull_conflict_accepted_overwrites_and_backs_up(env):
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "synced-point")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)

    push_as_friend(env, "friend-newer")
    write_save(save_dir, "played-offline")

    result, state = do_pull(cfg, state, log, confirm_yes, backups)

    assert result == SyncResult.PULLED
    assert (save_dir / f"{WORLD}.sav").read_bytes() == b"friend-newer"
    assert state["last_applied_version"] == 2
    # The un-shared local session was backed up before being replaced.
    backed_up = [p for p in backups.rglob(f"{WORLD}.sav")]
    assert any(p.read_bytes() == b"played-offline" for p in backed_up)


def test_pull_unchanged_local_needs_no_confirmation(env):
    """If the local save still matches last_hash, pulling never prompts."""
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "synced-point")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)
    push_as_friend(env, "friend-newer")

    def confirm_boom(title, body):
        raise AssertionError("should not prompt when local save is unchanged")

    result, state = do_pull(cfg, state, log, confirm_boom, backups)
    assert result == SyncResult.PULLED
    assert state["last_applied_version"] == 2


def test_pull_manifest_without_files(env):
    """Cloud client synced version.json before the save files: fail soft."""
    cfg, state, save_dir, sync_dir, backups = env
    from app.core.storage import write_json
    write_json(sync_dir / paths.MANIFEST_NAME, {
        "version": 5, "last_editor": "Bram",
        "timestamp": "2026-07-08T10:00:00+00:00", "world_name": WORLD,
    })
    _, log = logs()
    result, state = do_pull(cfg, state, log, confirm_yes, backups)
    assert result == SyncResult.MISSING_FILES
    assert state["last_applied_version"] == 0


# ---------------------------------------------------------------------------
# status
# ---------------------------------------------------------------------------

def test_status_transitions(env):
    cfg, state, save_dir, sync_dir, backups = env
    assert get_status(cfg, state).kind == "no_shared"

    push_as_friend(env)
    snapshot = get_status(cfg, state)
    assert snapshot.kind == "behind"
    assert snapshot.shared_version == 1
    assert snapshot.last_editor == "Bram"

    _, log = logs()
    _, state = do_pull(cfg, state, log, confirm_yes, backups)
    assert get_status(cfg, state).kind == "up_to_date"

    cfg2 = dict(cfg, sync_dir=str(sync_dir / "nope"))
    assert get_status(cfg2, state).kind == "folder_missing"


def test_push_stamps_manifest_schema(env):
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "s1")
    _, log = logs()
    do_push(cfg, state, log, confirm_yes, backups)
    from app.core.sync import MANIFEST_SCHEMA
    assert read_manifest(sync_dir)["app_schema"] == MANIFEST_SCHEMA
    assert get_status(cfg, state).manifest_schema == MANIFEST_SCHEMA


# ---------------------------------------------------------------------------
# history amendments (session notes / duration / flair)
# ---------------------------------------------------------------------------

def test_amend_history_adds_note_and_duration(env):
    from app.core.sync import amend_history_entry
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "s1")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)

    assert amend_history_entry(sync_dir, 1, note="Built the gatehouse", duration_s=4520)
    manifest = read_manifest(sync_dir)
    entry = manifest["history"][0]
    assert entry["note"] == "Built the gatehouse"
    assert entry["duration_s"] == 4520
    # protocol fields untouched
    assert manifest["version"] == 1
    assert entry["version"] == 1
    assert (sync_dir / f"{WORLD}.sav").read_bytes() == b"s1"


def test_amend_history_rejects_unknown_fields_and_missing_versions(env):
    from app.core.sync import amend_history_entry
    cfg, state, save_dir, sync_dir, backups = env
    write_save(save_dir, "s1")
    _, log = logs()
    _, state = do_push(cfg, state, log, confirm_yes, backups)

    before = read_manifest(sync_dir)
    assert not amend_history_entry(sync_dir, 1, last_editor="Evil", timestamp="1999")
    assert not amend_history_entry(sync_dir, 42, note="ghost session")
    assert not amend_history_entry(sync_dir, 1, note="")
    assert read_manifest(sync_dir) == before


def test_amend_history_without_manifest(env):
    from app.core.sync import amend_history_entry
    cfg, state, save_dir, sync_dir, backups = env
    assert not amend_history_entry(sync_dir, 1, note="nothing there")


def test_backup_pruning(env):
    cfg, state, save_dir, sync_dir, backups = env
    from app.core.sync import _backup_files, BACKUPS_TO_KEEP
    write_save(save_dir, "x")
    files = [save_dir / f"{WORLD}.sav"]
    for i in range(BACKUPS_TO_KEEP + 5):
        _backup_files(files, f"test{i:03d}", backups)
    assert len(list(backups.iterdir())) == BACKUPS_TO_KEEP
