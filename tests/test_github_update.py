"""Self-update from GitHub releases: pick the right exe, verify it, never apply junk."""

import hashlib

from app import channel
from app.core import github_update as gu

EXE = b"MZ" + b"x" * 1_200_000
SHA = hashlib.sha256(EXE).hexdigest()


def release(tag="v2.2.0", **over):
    data = {
        "tag_name": tag, "draft": False, "prerelease": False,
        "body": "## Fixes\n- Valheim waits for the real game now",
        "assets": [
            {"name": "WorldSync.exe", "size": len(EXE), "digest": "sha256:" + SHA,
             "browser_download_url": "https://example.invalid/WorldSync.exe"},
            {"name": "WorldSync-Nexus.exe", "size": len(EXE), "digest": "sha256:" + SHA,
             "browser_download_url": "https://example.invalid/WorldSync-Nexus.exe"},
        ],
    }
    data.update(over)
    return lambda url: data


def fake_download(payload=EXE):
    def download(url, dest):
        dest.write_bytes(payload)
        return hashlib.sha256(payload).hexdigest()
    return download


def test_newer_release_is_found_with_its_checksum():
    r = gu.latest_release("2.1.2", fetch=release())
    assert r["version"] == "2.2.0" and r["url"].endswith("/WorldSync.exe")
    assert r["sha256"] == SHA and r["notes"] == "Fixes"


def test_same_or_older_release_is_ignored():
    assert gu.latest_release("2.2.0", fetch=release()) is None
    assert gu.latest_release("3.0.0", fetch=release()) is None


def test_drafts_and_prereleases_are_ignored():
    assert gu.latest_release("2.1.2", fetch=release(prerelease=True)) is None
    assert gu.latest_release("2.1.2", fetch=release(draft=True)) is None


def test_nexus_build_updates_to_the_nexus_exe(monkeypatch):
    monkeypatch.setattr(channel, "CHANNEL", "nexus")
    assert gu.latest_release("2.1.2", fetch=release())["url"].endswith("WorldSync-Nexus.exe")


def test_download_is_verified_and_ready_to_apply(tmp_path):
    r = gu.latest_release("2.1.2", fetch=release())
    info = gu.fetch_update(r, tmp_path, download=fake_download())
    assert info.exe_path == tmp_path / "WorldSync-2.2.0.exe"
    assert info.exe_path.read_bytes() == EXE and info.published_by == gu.PUBLISHER
    assert not list(tmp_path.glob("*.part"))


def test_tampered_download_is_dropped(tmp_path):
    r = gu.latest_release("2.1.2", fetch=release())
    bad = b"MZ" + b"y" * (len(EXE) - 2)            # right size, wrong bytes
    assert gu.fetch_update(r, tmp_path, download=fake_download(bad)) is None
    assert not list(tmp_path.iterdir())


def test_truncated_download_is_dropped(tmp_path):
    r = gu.latest_release("2.1.2", fetch=release())
    assert gu.fetch_update(r, tmp_path, download=fake_download(EXE[:5000])) is None


def test_checker_asks_github_at_most_every_few_hours():
    now = [0.0]
    c = gu.Checker(every_s=100, clock=lambda: now[0])
    assert c.due()
    c._last = now[0]
    now[0] = 50
    assert not c.due()
    now[0] = 100
    assert c.due()


def test_release_notes_come_from_the_changelog():
    import importlib.util
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "tools" / "release_notes.py"
    spec = importlib.util.spec_from_file_location("release_notes", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    text = "# Changelog\n\n## 2.1.2 - 2026-10-07\n\nFixes.\n\n- a\n\n## 2.1.1 - x\n\n- old\n"
    assert mod.section("v2.1.2", text) == "Fixes.\n\n- a"
    assert gu._notes("**Full Changelog**: https://x\n") == ""
