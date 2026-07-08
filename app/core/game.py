"""Launching RuneScape: Dragonwilds and watching for its process."""

import logging
import os
import subprocess
import time
from pathlib import Path

try:
    import psutil
except ImportError:  # pragma: no cover - bundled in the shipped exe
    psutil = None

from . import paths

log = logging.getLogger("dwsync.game")

START_TIMEOUT_S = 120   # how long Steam may take to actually start the game
START_POLL_S = 1.0
EXIT_POLL_S = 3.0
SAVE_FLUSH_GRACE_S = 3.0  # let the game finish writing its save after exit


def process_watch_available() -> bool:
    return psutil is not None


def find_game_process():
    if not psutil:
        return None
    for p in psutil.process_iter(["name"]):
        try:
            if p.info["name"] and p.info["name"].lower() == paths.GAME_PROCESS_NAME.lower():
                return p
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


def launch_game(cfg) -> str:
    """Start the game; returns a short description of how it was launched.

    Falls back to the Steam URI if the configured exe is missing or fails.
    """
    exe_path = cfg.get("exe_path")
    if exe_path:
        exe = Path(exe_path)
        if exe.exists():
            try:
                subprocess.Popen([str(exe)], cwd=str(exe.parent))
                return "exe"
            except OSError as e:
                log.warning("Launching %s failed (%s); falling back to Steam.", exe, e)
        else:
            log.warning("Configured exe %s not found; falling back to Steam.", exe)
    app_id = cfg.get("steam_app_id", paths.STEAM_APP_ID)
    os.startfile(f"steam://rungameid/{app_id}")  # noqa: S606 - intended launch
    return "steam"


def wait_for_game_start(timeout_s: float = START_TIMEOUT_S):
    """Poll until the game process appears; returns it, or None on timeout."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        proc = find_game_process()
        if proc:
            return proc
        time.sleep(START_POLL_S)
    return None


def wait_for_game_exit(proc):
    """Block until the game process ends, then give it a moment to flush saves."""
    while proc.is_running():
        time.sleep(EXIT_POLL_S)
    time.sleep(SAVE_FLUSH_GRACE_S)
