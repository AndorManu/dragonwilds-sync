"""World version history, saga stats/chronicle, and Discord RP framing."""

import json
import struct

from app.core import discordrp, saga, worldhistory

WORLD = "Minhalla"


def write_save(folder, content):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{WORLD}.sav").write_bytes(content.encode())
    (folder / f"{WORLD}.sav.backup").write_bytes((content + "-b").encode())


# ---------------------------------------------------------------------------
# world history
# ---------------------------------------------------------------------------

def test_archive_and_list(tmp_path):
    write_save(tmp_path, "v5-data")
    assert worldhistory.archive_version(tmp_path, WORLD, 5)
    versions = worldhistory.list_versions(tmp_path)
    assert len(versions) == 1
    assert versions[0].version == 5
    assert versions[0].file_count == 2
    assert (versions[0].path / f"{WORLD}.sav").read_bytes() == b"v5-data"


def test_archive_prunes_to_keep(tmp_path):
    for v in range(1, 6):
        write_save(tmp_path, f"v{v}-data")
        worldhistory.archive_version(tmp_path, WORLD, v, keep=3)
    versions = worldhistory.list_versions(tmp_path)
    assert [av.version for av in versions] == [5, 4, 3]


def test_archive_nothing_to_copy(tmp_path):
    assert not worldhistory.archive_version(tmp_path, WORLD, 1)
    assert worldhistory.list_versions(tmp_path) == []


def test_archived_version_restores_via_backups_module(tmp_path):
    from app.core.backups import restore_backup
    write_save(tmp_path, "old-glory")
    worldhistory.archive_version(tmp_path, WORLD, 7)
    write_save(tmp_path, "newer")
    save_dir = tmp_path / "local"
    write_save(save_dir, "current-local")
    archived = worldhistory.list_versions(tmp_path)[0]
    n = restore_backup(archived.path, save_dir, WORLD, tmp_path / "bk")
    assert n == 2
    assert (save_dir / f"{WORLD}.sav").read_bytes() == b"old-glory"


# ---------------------------------------------------------------------------
# saga
# ---------------------------------------------------------------------------

def test_bump_and_read_stats(tmp_path):
    saga.bump_stats(tmp_path, "Andor", 3600)
    saga.bump_stats(tmp_path, "Andor", 1800)
    saga.bump_stats(tmp_path, "Bram", None)
    stats = saga.read_stats(tmp_path)
    assert stats["Andor"] == {"sessions": 2, "seconds": 5400}
    assert stats["Bram"] == {"sessions": 1, "seconds": 0}


def test_combined_stats_prefers_accumulator(tmp_path):
    manifest = {"history": [{"editor": "Elise", "duration_s": 100}]}
    stats, all_time = saga.combined_stats(tmp_path, manifest)
    assert not all_time and stats["Elise"]["sessions"] == 1
    saga.bump_stats(tmp_path, "Andor", 60)
    stats, all_time = saga.combined_stats(tmp_path, manifest)
    assert all_time and "Andor" in stats


def test_chronicle_html_content_and_escaping(tmp_path):
    manifest = {
        "version": 14,
        "history": [
            {"editor": "Bram", "version": 13, "character": "Grimjaw",
             "timestamp": "2026-07-08T10:00:00+00:00",
             "note": "Tamed the <salamander>"},
        ],
    }
    text = saga.chronicle_html(WORLD, manifest,
                               {"Bram": {"sessions": 9, "seconds": 7200}}, True)
    assert "The Saga of Minhalla" in text
    assert "Grimjaw" in text
    assert "&lt;salamander&gt;" in text and "<salamander>" not in text
    assert "9 sessions" in text and "2.0 h" in text


def test_write_saga_file(tmp_path):
    assert saga.write_saga(tmp_path, WORLD, {"version": 1, "history": []})
    assert (tmp_path / saga.SAGA_NAME).exists()


# ---------------------------------------------------------------------------
# discord rp framing
# ---------------------------------------------------------------------------

def test_frame_encoding_roundtrip():
    frame = discordrp.encode_frame(discordrp.OP_HANDSHAKE,
                                   {"v": 1, "client_id": "123"})
    op, length = struct.unpack("<II", frame[:8])
    assert op == 0
    payload = json.loads(frame[8:8 + length])
    assert payload["client_id"] == "123"


def test_activity_payload_truncates_and_stamps():
    p = discordrp.activity_payload(4242, "d" * 300, "s" * 300, 1234567890)
    activity = p["args"]["activity"]
    assert len(activity["details"]) == 120
    assert activity["timestamps"]["start"] == 1234567890
    assert p["args"]["pid"] == 4242
    assert p["cmd"] == "SET_ACTIVITY"


def test_clear_payload():
    p = discordrp.clear_payload(1)
    assert p["args"]["activity"] is None


def test_rich_presence_unavailable_without_id():
    rp = discordrp.RichPresence("")
    assert not rp.available
    rp.set_playing("Minhalla")   # must not raise
    rp.clear()
