"""Opt-in, anonymous reports: does WorldSync actually work for each game?

Off until the player says yes (asked once, changeable in Settings). When on,
the app sends small events such as "valheim: shared OK" or "palworld: pull
failed" plus an optional thumbs up/down after a game's first share. That's
how beta games earn "tested" from real groups instead of guesses.

What a report contains, and nothing else:
  install_id   a random id made on this PC when you opt in (not your Steam id,
               not your name, not tied to anything)
  app_version, os (e.g. "Windows 11"), game id, event name
  props        only whitelisted keys below: a result code, counts, a rating,
               and for feedback an optional comment you typed yourself

Never sent: player names, world names, file paths, shared-folder names,
invite codes or save contents. Sending is fire-and-forget on a background
thread with a short timeout; a failure is silently dropped and can never
affect a sync.
"""

import json
import logging
import platform
import threading
import urllib.request
import uuid

log = logging.getLogger("dwsync.telemetry")

# The reporting backend (Supabase). The key is the public "publishable" key: the
# database only lets it add rows to the events table, it can't read anything back.
ENDPOINT = "https://gqlcpgosdkwfgmiqcymy.supabase.co/rest/v1/events"
API_KEY = "sb_publishable_HBviDO2TiQkI4npN7ACZOQ_8b-iCBlF"
TIMEOUT_S = 4

EVENTS = {
    "app_start", "game_added", "world_created", "world_joined", "push", "pull",
    "conflict", "game_launch", "feedback", "error",
}
PROP_KEYS = {"result", "found_folder", "worlds_found", "rating", "comment",
             "direction", "kind", "first_time"}
COMMENT_MAX = 500


def available() -> bool:
    return bool(ENDPOINT and API_KEY)


def enabled(cfg: dict | None) -> bool:
    return available() and bool((cfg or {}).get("telemetry")) and bool((cfg or {}).get("install_id"))


def opt_in(cfg: dict):
    cfg["telemetry"] = True
    if not cfg.get("install_id"):
        cfg["install_id"] = uuid.uuid4().hex


def opt_out(cfg: dict):
    cfg["telemetry"] = False


def os_label() -> str:
    if platform.system() != "Windows":
        return platform.system() or "unknown"
    try:
        build = int(platform.version().split(".")[-1])
    except ValueError:
        build = 0
    return "Windows 11" if build >= 22000 else f"Windows {platform.release()}"


def build_payload(cfg: dict, event: str, game: str | None, version: str, **props) -> dict:
    """The exact JSON that leaves the PC. Unknown keys are dropped here."""
    clean = {}
    for key, value in props.items():
        if key not in PROP_KEYS or value is None:
            continue
        if key == "comment":
            value = str(value).strip()[:COMMENT_MAX]
            if not value:
                continue
        elif isinstance(value, (int, float, bool)):
            pass
        else:
            value = str(value)[:40]
        clean[key] = value
    return {
        "install_id": cfg.get("install_id"),
        "app_version": version,
        "os": os_label(),
        "game": game,
        "event": event,
        "props": clean,
    }


def _post(payload: dict):
    try:
        req = urllib.request.Request(
            ENDPOINT, data=json.dumps(payload).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "apikey": API_KEY,
                     "Authorization": f"Bearer {API_KEY}", "Prefer": "return=minimal",
                     "User-Agent": "WorldSync"})
        urllib.request.urlopen(req, timeout=TIMEOUT_S).close()
    except Exception as e:      # never let reporting matter
        log.debug("report not sent: %s", e)


def send(cfg: dict | None, event: str, game: str | None = None, version: str = "",
         **props) -> dict | None:
    """Queue one report if the player opted in. Returns the payload (for tests)."""
    if event not in EVENTS or not enabled(cfg):
        return None
    payload = build_payload(cfg, event, game, version, **props)
    threading.Thread(target=_post, args=(payload,), daemon=True, name="report").start()
    return payload
