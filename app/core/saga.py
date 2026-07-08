"""The saga: all-time per-player stats and an exportable chronicle.

The manifest's history list caps at 50 entries, so honest all-time totals
live in a small ``stats.json`` accumulator in the shared folder, bumped on
every push. The chronicle turns everyone's session notes into a shareable
HTML page written beside the saves. All fail-soft, all after the sync core.
"""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

from .storage import read_json, write_json

log = logging.getLogger("dwsync.saga")

STATS_NAME = "stats.json"
SAGA_NAME = "saga.html"


def bump_stats(sync_dir, player: str, seconds: int | None) -> dict:
    """Record one finished session for `player`; returns the new stats."""
    path = Path(sync_dir) / STATS_NAME
    stats = read_json(path, {}) or {}
    entry = stats.setdefault(player, {"sessions": 0, "seconds": 0})
    entry["sessions"] = int(entry.get("sessions", 0)) + 1
    entry["seconds"] = int(entry.get("seconds", 0)) + int(seconds or 0)
    try:
        write_json(path, stats)
    except OSError:
        log.warning("Could not write stats.json", exc_info=True)
    return stats


def read_stats(sync_dir) -> dict:
    return read_json(Path(sync_dir) / STATS_NAME, {}) or {}


def aggregate_from_history(manifest) -> dict:
    """Fallback totals from the (capped) manifest history."""
    stats = {}
    for entry in (manifest or {}).get("history", []):
        who = entry.get("editor")
        if not who:
            continue
        slot = stats.setdefault(who, {"sessions": 0, "seconds": 0})
        slot["sessions"] += 1
        slot["seconds"] += int(entry.get("duration_s") or 0)
    return stats


def combined_stats(sync_dir, manifest) -> tuple[dict, bool]:
    """(stats, all_time). Prefers the accumulator; falls back to history."""
    stats = read_stats(sync_dir)
    if stats:
        return stats, True
    return aggregate_from_history(manifest), False


def _fmt_hours(seconds) -> str:
    hours = (seconds or 0) / 3600
    return f"{hours:.1f} h" if hours >= 0.1 else "—"


def _humanize(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone().strftime("%d %b %Y, %H:%M")
    except (TypeError, ValueError):
        return ""


_SAGA_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>The Saga of {world}</title>
<style>
 :root{{color-scheme:dark}}
 body{{margin:0;background:#0A0D12;color:#ECEFF3;
   font-family:Georgia,'Times New Roman',serif;padding:26px}}
 .wrap{{max-width:640px;margin:0 auto}}
 h1{{font-size:30px;margin:0;color:#E6C892;font-weight:600}}
 .sub{{color:#9AA7B6;font-size:14px;margin:4px 0 24px;
   font-family:-apple-system,Segoe UI,sans-serif}}
 h2{{font-size:13px;letter-spacing:2px;color:#E8A23D;text-transform:uppercase;
   font-family:-apple-system,Segoe UI,sans-serif;margin:26px 0 10px}}
 .stats{{display:flex;flex-wrap:wrap;gap:10px}}
 .stat{{background:#12191F;border:1px solid #222E39;border-radius:12px;
   padding:12px 16px;min-width:130px;
   font-family:-apple-system,Segoe UI,sans-serif}}
 .stat b{{display:block;font-size:15px}}
 .stat span{{color:#9AA7B6;font-size:12px}}
 .entry{{border-left:2px solid #2A3844;padding:6px 0 6px 16px;margin:10px 0}}
 .who{{font-family:-apple-system,Segoe UI,sans-serif;font-size:13px;
   color:#9AA7B6}}
 .who b{{color:#ECEFF3}}
 .note{{font-size:17px;font-style:italic;color:#E6C892;margin:2px 0}}
 .foot{{color:#5E6B7A;font-size:11px;text-align:center;margin-top:30px;
   font-family:-apple-system,Segoe UI,sans-serif}}
</style></head><body><div class="wrap">
 <h1>The Saga of {world}</h1>
 <div class="sub">{summary}</div>
 <h2>The fellowship</h2>
 <div class="stats">{stats}</div>
 <h2>The chronicle</h2>
 {entries}
 <div class="foot">Written by Dragonwilds Sync · {updated}</div>
</div></body></html>
"""


def chronicle_html(world_name, manifest, stats: dict, all_time: bool) -> str:
    e = html.escape
    history = (manifest or {}).get("history", [])

    stat_cards = []
    for player, s in sorted(stats.items(), key=lambda kv: -kv[1].get("seconds", 0)):
        stat_cards.append(
            f'<div class="stat"><b>{e(player)}</b>'
            f'<span>{s.get("sessions", 0)} sessions · {_fmt_hours(s.get("seconds"))}</span></div>')

    entries = []
    for entry in reversed(history):
        who = e(entry.get("editor", "?"))
        char = entry.get("character")
        as_char = f" as {e(char)}" if char else ""
        note = entry.get("note")
        note_html = f'<div class="note">“{e(note)}”</div>' if note else ""
        entries.append(
            f'<div class="entry">{note_html}'
            f'<div class="who"><b>{who}</b>{as_char} · v{entry.get("version", "?")} '
            f'· {_humanize(entry.get("timestamp", ""))}</div></div>')

    total_sessions = sum(s.get("sessions", 0) for s in stats.values())
    scope = "all time" if all_time else f"the last {len(history)} sessions"
    summary = (f"v{(manifest or {}).get('version', '?')} · "
               f"{total_sessions} sessions across {scope}")

    return _SAGA_TEMPLATE.format(
        world=e(world_name), summary=summary,
        stats="".join(stat_cards) or '<div class="stat"><b>No one yet</b></div>',
        entries="".join(entries) or '<div class="who">The first page is unwritten.</div>',
        updated=datetime.now().strftime("%d %b %Y, %H:%M"))


def write_saga(sync_dir, world_name, manifest) -> Path | None:
    try:
        stats, all_time = combined_stats(sync_dir, manifest)
        path = Path(sync_dir) / SAGA_NAME
        path.write_text(chronicle_html(world_name, manifest, stats, all_time),
                        encoding="utf-8")
        return path
    except OSError:
        log.warning("Could not write saga", exc_info=True)
        return None
