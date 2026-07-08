"""Human-friendly formatting helpers for the UI."""

import hashlib
from datetime import datetime, timezone

from . import theme


def parse_utc(ts: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def humanize(ts: str) -> str:
    """'just now' / '25 min ago' / '3 h ago' / 'Tue 14:02' / '3 Jul'."""
    dt = parse_utc(ts)
    if dt is None:
        return ""
    now = datetime.now(timezone.utc)
    delta = now - dt
    seconds = delta.total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)} min ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)} h ago"
    local = dt.astimezone()
    if seconds < 7 * 86400:
        return local.strftime("%a %H:%M")
    return f"{local.day} {local.strftime('%b')}"


def initials(name: str) -> str:
    parts = [p for p in (name or "?").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper() if len(parts[0]) > 1 else parts[0].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def name_color(name: str) -> str:
    digest = hashlib.sha1((name or "").lower().encode()).digest()
    return theme.AVATAR_COLORS[digest[0] % len(theme.AVATAR_COLORS)]
