"""Live presence and turn reservation via tiny files in the shared folder.

``playing.json`` — written when someone starts a session, removed when their
save is shared. ``next.json`` — an "I've got next" claim. Both are advisory:
they warn people up front, while the sync core's conflict checks remain the
actual safety net. Every function here fails soft — a cloud hiccup must
never break a session.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from .storage import read_json, write_json

log = logging.getLogger("dwsync.presence")

PLAYING_NAME = "playing.json"
NEXT_NAME = "next.json"
PLAYING_STALE_S = 4 * 3600    # a crash shouldn't block friends for more than a session
NEXT_STALE_S = 12 * 3600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _age_seconds(ts: str) -> float | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - dt).total_seconds()
    except (TypeError, ValueError):
        return None


def _read_fresh(path: Path, stale_s: float) -> dict | None:
    data = read_json(path)
    if not isinstance(data, dict) or not data.get("player"):
        return None
    age = _age_seconds(data.get("since", ""))
    if age is None or age > stale_s:
        return None
    data["age_s"] = age
    return data


def start_playing(sync_dir, player: str, emoji: str = ""):
    try:
        write_json(Path(sync_dir) / PLAYING_NAME,
                   {"player": player, "emoji": emoji, "since": _now()})
    except OSError:
        log.warning("Could not write presence file", exc_info=True)


def stop_playing(sync_dir, player: str):
    """Remove our own presence marker (never someone else's)."""
    path = Path(sync_dir) / PLAYING_NAME
    try:
        data = read_json(path)
        if isinstance(data, dict) and data.get("player") not in (None, player):
            return
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not clear presence file", exc_info=True)


def who_is_playing(sync_dir) -> dict | None:
    return _read_fresh(Path(sync_dir) / PLAYING_NAME, PLAYING_STALE_S)


def claim_next(sync_dir, player: str, emoji: str = ""):
    try:
        write_json(Path(sync_dir) / NEXT_NAME,
                   {"player": player, "emoji": emoji, "since": _now()})
    except OSError:
        log.warning("Could not write turn claim", exc_info=True)


def clear_next(sync_dir, player: str | None = None):
    """Clear the claim; if `player` given, only when it's theirs."""
    path = Path(sync_dir) / NEXT_NAME
    try:
        if player is not None:
            data = read_json(path)
            if isinstance(data, dict) and data.get("player") != player:
                return
        path.unlink(missing_ok=True)
    except OSError:
        log.warning("Could not clear turn claim", exc_info=True)


def who_has_next(sync_dir) -> dict | None:
    return _read_fresh(Path(sync_dir) / NEXT_NAME, NEXT_STALE_S)
