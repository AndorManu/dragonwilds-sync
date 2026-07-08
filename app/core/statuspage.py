"""A tiny self-contained status page written into the shared folder.

The shared folder is already hosted storage every friend can reach — so a
single ``status.html`` there is a zero-backend way to check, from a phone's
Google Drive / Dropbox app, who's playing and whether a save is waiting.
Written on push and on presence changes; entirely optional.
"""

import html
import logging
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("dwsync.statuspage")

STATUS_NAME = "status.html"

_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{world} · Dragonwilds Sync</title>
<style>
 :root{{color-scheme:dark}}
 body{{margin:0;background:#0A0D12;color:#ECEFF3;
   font-family:-apple-system,Segoe UI,Roboto,sans-serif;padding:22px}}
 .wrap{{max-width:520px;margin:0 auto}}
 h1{{font-size:26px;margin:0 0 2px;color:#E6C892}}
 .sub{{color:#9AA7B6;font-size:13px;margin-bottom:20px}}
 .card{{background:#12191F;border:1px solid #222E39;border-radius:14px;
   padding:16px 18px;margin-bottom:14px}}
 .status{{font-size:19px;font-weight:600}}
 .dot{{display:inline-block;width:9px;height:9px;border-radius:50%;
   margin-right:8px;vertical-align:middle}}
 .muted{{color:#9AA7B6;font-size:13px;margin-top:4px}}
 .feed div{{padding:9px 0;border-top:1px solid #19222C;font-size:14px}}
 .feed div:first-child{{border-top:none}}
 .who{{font-weight:600}} .when{{color:#5E6B7A;font-size:12px}}
 .note{{color:#E6C892;font-style:italic;font-size:13px}}
 .foot{{color:#5E6B7A;font-size:11px;text-align:center;margin-top:18px}}
</style></head><body><div class="wrap">
 <h1>{world}</h1>
 <div class="sub">Dragonwilds Sync · shared world status</div>
 <div class="card">
   <div class="status"><span class="dot" style="background:{dot}"></span>{headline}</div>
   <div class="muted">{detail}</div>
 </div>
 <div class="card feed">{feed}</div>
 <div class="foot">Updated {updated} · refresh to check again</div>
</div></body></html>
"""


def _humanize(ts: str) -> str:
    try:
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return ""
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 3600:
        return f"{max(1, int(secs // 60))} min ago"
    if secs < 86400:
        return f"{int(secs // 3600)} h ago"
    return dt.astimezone().strftime("%d %b %H:%M")


def render(world_name, manifest, playing, next_claim) -> str:
    e = html.escape
    if playing:
        dot, headline = "#F2B441", f"{e(playing.get('player', 'Someone'))} is playing now"
        detail = "Best wait for their save before you jump in."
    elif manifest:
        dot = "#3ECF8E"
        headline = f"Latest: v{manifest.get('version', '?')}"
        who = e(manifest.get("last_editor", "a friend"))
        detail = f"Last played by {who} {_humanize(manifest.get('timestamp', ''))}."
        if next_claim:
            detail += f" {e(next_claim.get('player',''))} has called next turn."
    else:
        dot, headline, detail = "#5E6B7A", "No save shared yet", "Be the first to play."

    rows = []
    for entry in reversed((manifest or {}).get("history", [])[-8:]):
        note = entry.get("note")
        note_html = f'<div class="note">“{e(note)}”</div>' if note else ""
        rows.append(
            f'<div><span class="who">{e(entry.get("editor", "?"))}</span> '
            f'· v{entry.get("version", "?")} '
            f'<span class="when">{_humanize(entry.get("timestamp", ""))}</span>'
            f'{note_html}</div>')
    feed = "".join(rows) or '<div class="muted">No sessions yet.</div>'

    return _TEMPLATE.format(
        world=e(world_name), dot=dot, headline=headline, detail=detail,
        feed=feed, updated=datetime.now().strftime("%d %b %H:%M"))


def write(sync_dir, world_name, manifest, playing=None, next_claim=None) -> bool:
    """Best-effort; a status-page failure must never affect a sync."""
    try:
        path = Path(sync_dir) / STATUS_NAME
        path.write_text(render(world_name, manifest, playing, next_claim),
                        encoding="utf-8")
        return True
    except OSError:
        log.warning("Could not write status page", exc_info=True)
        return False
