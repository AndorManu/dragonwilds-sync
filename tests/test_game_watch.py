"""Watching the game: survive a Steam self-restart, and copy past short file locks."""

import shutil

from app.core import game, sync


class FakeProc:
    def __init__(self, polls_alive, pid=1):
        self.polls_alive, self.pid = polls_alive, pid

    def is_running(self):
        self.polls_alive -= 1
        return self.polls_alive >= 0


def _fast(monkeypatch):
    for name in ("EXIT_POLL_S", "START_POLL_S", "SAVE_FLUSH_GRACE_S"):
        monkeypatch.setattr(game, name, 0)


def test_waits_on_the_relaunched_game(monkeypatch):
    """valheim.exe started directly quits at once and Steam starts it again."""
    _fast(monkeypatch)
    first, real = FakeProc(1, pid=1), FakeProc(5, pid=2)
    found = iter([None, real])
    monkeypatch.setattr(game, "find_game_process", lambda names=None: next(found, None))
    game.wait_for_game_exit(first, ["valheim.exe"], relaunch_s=5)
    assert real.polls_alive < 0          # we waited for the real session to end


def test_returns_when_the_game_stays_closed(monkeypatch):
    _fast(monkeypatch)
    monkeypatch.setattr(game, "find_game_process", lambda names=None: None)
    proc = FakeProc(2)
    game.wait_for_game_exit(proc, ["raft.exe"], relaunch_s=0.05)
    assert proc.polls_alive < 0


def test_copy_waits_out_a_short_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "COPY_RETRY_S", 0)
    src = tmp_path / "a" / "Midgard.db"
    src.parent.mkdir()
    src.write_bytes(b"world")
    real_copy, calls = shutil.copy2, []

    def flaky(a, b):
        calls.append(a)
        if len(calls) < 3:
            raise PermissionError("in use by another process")
        return real_copy(a, b)
    monkeypatch.setattr(sync.shutil, "copy2", flaky)
    sync._copy_world([src], src.parent, tmp_path / "b")
    assert (tmp_path / "b" / "Midgard.db").read_bytes() == b"world"
    assert len(calls) == 3


def test_copy_gives_up_on_a_lasting_lock(monkeypatch, tmp_path):
    monkeypatch.setattr(sync, "COPY_RETRY_S", 0)
    src = tmp_path / "a" / "Midgard.db"
    src.parent.mkdir()
    src.write_bytes(b"world")

    def locked(a, b):
        raise PermissionError("in use")
    monkeypatch.setattr(sync.shutil, "copy2", locked)
    try:
        sync._copy_world([src], src.parent, tmp_path / "b")
    except PermissionError:
        pass
    else:
        raise AssertionError("a lasting lock must still fail loudly")


def test_v_rising_cloud_saves_are_found(tmp_path):
    """A Private Game with cloud saving on lives under CloudSaves/v3/<steam id>."""
    import os
    import time
    from app.core import games
    locallow = tmp_path / "LocalLow"
    old = locallow / "Stunlock Studios" / "VRising" / "Saves" / "v3" / "OldGame"
    old.mkdir(parents=True)
    (old / "ServerHostSettings.json").write_text('{"Name": "Old"}')
    past = time.time() - 86400 * 30
    os.utime(old / "ServerHostSettings.json", (past, past))
    os.utime(old, (past, past))
    cloud = locallow / "Stunlock Studios" / "VRising" / "CloudSaves" / "v3" / "76561198000000000"
    game_dir = cloud / "f3c1a2b4-castle"
    game_dir.mkdir(parents=True)
    (game_dir / "ServerHostSettings.json").write_text('{"Name": "Castle"}')
    tokens = {k: str(tmp_path / "none") for k in
              ("LOCALAPPDATA", "APPDATA", "SAVEDGAMES", "DOCUMENTS", "PROGRAMFILESX86", "USERPROFILE")}
    tokens["LOCALLOW"] = str(locallow)
    found = games.default_save_dir(games.V_RISING, tokens)
    assert found == cloud                     # the folder with the recent game wins
    assert [w.id for w in games.discover_worlds(games.V_RISING, found)] == ["f3c1a2b4-castle"]
