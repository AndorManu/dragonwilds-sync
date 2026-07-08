"""'Test my setup' — one pass that catches the things that trip up friends.

Pure checks, no side effects beyond writing (and deleting) a probe file to
confirm the shared folder is writable. Returns a list of results the UI can
render as a checklist.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from . import clouds, game, health, paths
from .sync import get_shared_manifest, world_files

OK, WARN, FAIL = "ok", "warn", "fail"


@dataclass
class Check:
    label: str
    status: str          # ok | warn | fail
    detail: str


def _writable(folder: Path) -> bool:
    probe = folder / ".dwsync_write_test"
    try:
        probe.write_text("ok", encoding="ascii")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False


def run(cfg: dict, world: dict) -> list[Check]:
    """cfg is the v2 global config; world is the active world dict."""
    checks: list[Check] = []
    save_dir = Path(cfg.get("local_save_dir", ""))
    world_name = world.get("world_name", "")
    sync_dir = Path(world.get("sync_dir", ""))

    # 1. Save folder
    if save_dir.exists():
        checks.append(Check("Game save folder", OK, str(save_dir)))
    else:
        checks.append(Check("Game save folder", FAIL,
                            "Not found — set it in Settings."))

    # 2. The world save itself
    hp = health.check_local_save(save_dir, world_name)
    if hp.ok:
        checks.append(Check(f"World save “{world_name}”", OK,
                            f"{hp.primary_size // 1024} KB"))
    elif not save_dir.exists():
        checks.append(Check(f"World save “{world_name}”", WARN,
                            "Can't check until the save folder is set."))
    else:
        checks.append(Check(f"World save “{world_name}”", WARN,
                            "Not on this PC yet — that's fine if a friend has "
                            "the latest. Hit Play to pull it in."))

    # 3. Shared folder present + writable
    if not sync_dir.exists():
        checks.append(Check("Shared folder", FAIL,
                            "Not found — is your cloud drive running?"))
    elif not _writable(sync_dir):
        checks.append(Check("Shared folder", FAIL,
                            "Found, but can't write to it — check folder permissions."))
    else:
        checks.append(Check("Shared folder", OK, str(sync_dir)))

    # 4. Cloud drive detected (is this folder actually inside one?)
    roots = clouds.detect_cloud_roots()
    if roots:
        inside = any(str(sync_dir).lower().startswith(str(r).lower())
                     for _, r in roots)
        if inside:
            checks.append(Check("Cloud drive", OK,
                                "Shared folder is inside " +
                                next(l for l, r in roots
                                     if str(sync_dir).lower().startswith(str(r).lower()))))
        else:
            checks.append(Check("Cloud drive", WARN,
                                "A cloud drive is running, but the shared folder "
                                "isn't inside it — friends may not receive your saves."))
    else:
        checks.append(Check("Cloud drive", WARN,
                            "None detected — saves won't reach friends without one."))

    # 5. Still-syncing check
    if sync_dir.exists() and health.shared_still_syncing(sync_dir, world_name):
        checks.append(Check("Sync state", WARN,
                            "The cloud folder looks like it's still downloading. "
                            "Give it a minute."))

    # 6. Game launch path
    exe = cfg.get("exe_path")
    if exe and Path(exe).is_file():
        checks.append(Check("Game launch", OK, "Direct exe configured."))
    elif game.find_game_process():
        checks.append(Check("Game launch", OK, "Game is running right now."))
    else:
        from . import steam
        found = steam.find_game_exe()
        if found:
            checks.append(Check("Game launch", OK, "Found your Steam install."))
        else:
            checks.append(Check("Game launch", WARN,
                                "Will launch via Steam. If that fails, set the "
                                "exe path in Settings."))
    return checks


def worst(checks: list[Check]) -> str:
    if any(c.status == FAIL for c in checks):
        return FAIL
    if any(c.status == WARN for c in checks):
        return WARN
    return OK
