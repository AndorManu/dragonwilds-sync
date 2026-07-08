"""Tests for the v1.2 feature services: semver, update, health, preflight,
nudges, checkpoints, and the status page. The sync core is untouched by all
of these — they wrap it or live beside it."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.core import backups, health, presence, semver, statuspage, update

WORLD = "Minhalla"


def make_save(folder: Path, content=b"x" * 4096):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{WORLD}.sav").write_bytes(content)
    (folder / f"{WORLD}.sav.backup").write_bytes(content + b"-b")


# ---------------------------------------------------------------------------
# semver
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cand,cur,expected", [
    ("1.1.0", "1.0.0", True),
    ("1.0.1", "1.0.0", True),
    ("2.0.0", "1.9.9", True),
    ("1.0.0", "1.0.0", False),
    ("1.0.0", "1.1.0", False),
    ("v1.2.0", "1.1.5", True),
    ("garbage", "1.0.0", False),
    ("1.0.0", "garbage", False),
])
def test_semver_is_newer(cand, cur, expected):
    assert semver.is_newer(cand, cur) is expected


# ---------------------------------------------------------------------------
# update
# ---------------------------------------------------------------------------

def test_publish_and_check_roundtrip(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    fake_exe = tmp_path / "DragonwildsSync.exe"
    fake_exe.write_bytes(b"MZ" + b"\x00" * 2_000_000)  # >1MB so it passes the guard

    update.publish(shared, "1.2.0", fake_exe, "Andor", notes="New stuff")
    info = update.check(shared, "1.1.0")
    assert info is not None
    assert info.version == "1.2.0"
    assert info.published_by == "Andor"
    assert info.exe_path.exists()


def test_check_ignores_same_or_older(tmp_path):
    shared = tmp_path / "shared"
    shared.mkdir()
    fake_exe = tmp_path / "app.exe"
    fake_exe.write_bytes(b"\x00" * 2_000_000)
    update.publish(shared, "1.1.0", fake_exe, "Andor")
    assert update.check(shared, "1.1.0") is None
    assert update.check(shared, "1.2.0") is None


def test_check_ignores_partial_download(tmp_path):
    shared = tmp_path / "shared"
    (shared / update.UPDATE_DIR_NAME).mkdir(parents=True)
    from app.core.storage import write_json
    write_json(shared / update.UPDATE_DIR_NAME / update.UPDATE_MANIFEST,
               {"version": "1.2.0", "filename": "DragonwildsSync-1.2.0.exe",
                "published_by": "Andor"})
    # tiny (still-syncing) exe -> ignored
    (shared / update.UPDATE_DIR_NAME / "DragonwildsSync-1.2.0.exe").write_bytes(b"partial")
    assert update.check(shared, "1.1.0") is None


def test_check_no_manifest(tmp_path):
    assert update.check(tmp_path, "1.0.0") is None


def test_swap_script_mentions_both_paths(tmp_path):
    staged = tmp_path / "new.exe"
    target = tmp_path / "cur.exe"
    script = update.build_swap_script(staged, target, tmp_path / "swap.bat")
    text = script.read_text()
    assert str(staged) in text and str(target) in text
    assert "copy" in text.lower()


# ---------------------------------------------------------------------------
# health
# ---------------------------------------------------------------------------

def test_healthy_save(tmp_path):
    make_save(tmp_path)
    hp = health.check_local_save(tmp_path, WORLD)
    assert hp.ok and hp.primary_size >= 1024


def test_zero_byte_save_is_unhealthy(tmp_path):
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / f"{WORLD}.sav").write_bytes(b"")
    hp = health.check_local_save(tmp_path, WORLD)
    assert not hp.ok


def test_missing_save_is_unhealthy(tmp_path):
    assert not health.check_local_save(tmp_path, WORLD).ok


def test_shared_still_syncing_detects_partial(tmp_path):
    make_save(tmp_path)
    assert not health.shared_still_syncing(tmp_path, WORLD)
    (tmp_path / "Minhalla.sav.crdownload").write_bytes(b"...")
    assert health.shared_still_syncing(tmp_path, WORLD)


def test_shared_still_syncing_detects_zero_byte_world_file(tmp_path):
    (tmp_path / f"{WORLD}.sav").write_bytes(b"")
    assert health.shared_still_syncing(tmp_path, WORLD)


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------

def test_preflight_all_ok(tmp_path, monkeypatch):
    from app.core import preflight, clouds
    save_dir = tmp_path / "saves"
    shared = tmp_path / "cloud" / "DW"
    make_save(save_dir)
    shared.mkdir(parents=True)
    monkeypatch.setattr(clouds, "detect_cloud_roots",
                        lambda: [("Test Drive", tmp_path / "cloud")])
    cfg = {"local_save_dir": str(save_dir), "exe_path": None}
    world = {"world_name": WORLD, "sync_dir": str(shared)}
    checks = preflight.run(cfg, world)
    labels = {c.label: c for c in checks}
    assert labels["Game save folder"].status == preflight.OK
    assert labels["Shared folder"].status == preflight.OK
    assert labels["Cloud drive"].status == preflight.OK
    assert preflight.worst(checks) in (preflight.OK, preflight.WARN)


def test_preflight_flags_missing_shared(tmp_path, monkeypatch):
    from app.core import preflight, clouds
    monkeypatch.setattr(clouds, "detect_cloud_roots", lambda: [])
    cfg = {"local_save_dir": str(tmp_path), "exe_path": None}
    world = {"world_name": WORLD, "sync_dir": str(tmp_path / "gone")}
    checks = preflight.run(cfg, world)
    assert preflight.worst(checks) == preflight.FAIL


# ---------------------------------------------------------------------------
# nudges
# ---------------------------------------------------------------------------

def test_nudge_addressed_to_recipient(tmp_path):
    presence.send_nudge(tmp_path, "Andor", "Bram", "🐉")
    assert presence.read_nudge_for(tmp_path, "Bram")["player"] == "Andor"
    assert presence.read_nudge_for(tmp_path, "Elise") is None
    assert presence.read_nudge_for(tmp_path, "Andor") is None  # sender never nudged


def test_nudge_clear(tmp_path):
    presence.send_nudge(tmp_path, "Andor", "Bram")
    presence.clear_nudge(tmp_path)
    assert presence.read_nudge_for(tmp_path, "Bram") is None


def test_stale_nudge_ignored(tmp_path):
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(timespec="seconds")
    (tmp_path / presence.NUDGE_NAME).write_text(
        json.dumps({"player": "Andor", "to": "Bram", "since": old}))
    assert presence.read_nudge_for(tmp_path, "Bram") is None


# ---------------------------------------------------------------------------
# checkpoints
# ---------------------------------------------------------------------------

def test_create_and_list_checkpoint(tmp_path):
    save = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(save)
    info = backups.create_checkpoint(save, WORLD, "Before the dragon", root)
    assert info and info.name == "Before the dragon" and info.is_checkpoint
    listed = backups.list_checkpoints(root)
    assert len(listed) == 1 and listed[0].name == "Before the dragon"
    # checkpoint.json is metadata, not counted as a save file
    assert listed[0].file_count == 2


def test_checkpoints_excluded_from_regular_backups(tmp_path):
    save = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(save)
    backups.create_checkpoint(save, WORLD, "cp", root)
    assert backups.list_backups(root) == []


def test_restore_checkpoint_skips_metadata(tmp_path):
    save = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(save, b"original" + b"x" * 4096)
    cp = backups.create_checkpoint(save, WORLD, "cp", root)
    make_save(save, b"changed" + b"x" * 4096)
    n = backups.restore_backup(cp.path, save, WORLD, root)
    assert n == 2
    assert not (save / "checkpoint.json").exists()
    assert (save / f"{WORLD}.sav").read_bytes().startswith(b"original")


def test_delete_backup(tmp_path):
    save = tmp_path / "saves"
    root = tmp_path / "backups"
    make_save(save)
    cp = backups.create_checkpoint(save, WORLD, "cp", root)
    assert backups.delete_backup(cp.path)
    assert backups.list_checkpoints(root) == []


# ---------------------------------------------------------------------------
# status page
# ---------------------------------------------------------------------------

def test_status_page_renders_and_writes(tmp_path):
    manifest = {
        "version": 14, "last_editor": "Elise",
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "history": [
            {"editor": "Bram", "version": 13, "timestamp": "2026-07-08T10:00:00+00:00",
             "note": "Tamed the salamander"},
            {"editor": "Elise", "version": 14, "timestamp": "2026-07-08T12:00:00+00:00"},
        ],
    }
    assert statuspage.write(tmp_path, WORLD, manifest, playing=None)
    text = (tmp_path / statuspage.STATUS_NAME).read_text(encoding="utf-8")
    assert "Minhalla" in text
    assert "Elise" in text
    assert "Tamed the salamander" in text
    assert "v14" in text


def test_status_page_escapes_html(tmp_path):
    manifest = {"version": 1, "last_editor": "<script>evil</script>",
                "timestamp": "2026-07-08T12:00:00+00:00", "history": []}
    statuspage.write(tmp_path, "<b>W</b>", manifest)
    text = (tmp_path / statuspage.STATUS_NAME).read_text(encoding="utf-8")
    assert "<script>evil" not in text
    assert "&lt;script&gt;" in text


def test_status_page_playing_state(tmp_path):
    statuspage.write(tmp_path, WORLD, None, playing={"player": "Bram"})
    text = (tmp_path / statuspage.STATUS_NAME).read_text(encoding="utf-8")
    assert "Bram is playing now" in text
