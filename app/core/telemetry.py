"""Anonymous reports: does WorldSync actually work for each game?

On by default, switched off with one checkbox in Settings (and said so on the
welcome screen and in the README). When on, the app sends small events such as "valheim: shared OK" or "palworld: pull
failed" plus an optional thumbs up/down after a game's first share. That's
how beta games earn "tested" from real groups instead of guesses.

What a report contains, and nothing else:
  install_id   a random id made on this PC (not your Steam id,
               not your name, not tied to anything)
  app_version, os (e.g. "Windows 11"), game id, event name
  props        only whitelisted keys below: a result code, a setup step, counts
               and timings (session minutes, world size in MB, sync time), how
               many players share the world, which kind of cloud drive (Google
               Drive / Dropbox / OneDrive / other), the system language (e.g.
               nl_NL), a rating, and for feedback a comment you typed yourself.
               For a crash: the error's type and the function it happened in,
               never the message (messages can contain file paths).

Never sent: player names, world names, file paths, shared-folder names,
invite codes, IP-derived location or save contents. Reports are deleted
after 12 months, and Settings → "Delete my reports" erases this PC's rows.
See PRIVACY.md. Sending is fire-and-forget on a background
thread with a short timeout; a failure is silently dropped and can never
affect a sync.
"""

import json
import locale
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
    "app_start", "first_run", "game_added", "world_created", "world_joined", "push",
    "pull", "conflict", "game_launch", "feedback", "error", "crash", "onboarding",
    "invite_created", "checkpoint", "restore", "guide_opened", "preflight",
    "update_applied", "tip_clicked", "game_requested", "turn",
}
PROP_KEYS = {"result", "found_folder", "worlds_found", "rating", "comment",
             "direction", "kind", "first_time", "step", "duration_min", "size_mb",
             "files", "sync_ms", "group_size", "cloud", "locale", "worst", "where",
             "source"}
FORGET_ENDPOINT = "https://gqlcpgosdkwfgmiqcymy.supabase.co/rest/v1/rpc/worldsync_forget"

# set by the controller so a crash anywhere can still be reported
_CTX = {"cfg": None, "version": ""}
COMMENT_MAX = 500


def available() -> bool:
    return bool(ENDPOINT and API_KEY)


def is_on(cfg: dict | None) -> bool:
    """The player's choice, or this build's default if they never touched it.

    The GitHub build defaults to on, the Nexus build to off (app/channel.py).
    """
    value = (cfg or {}).get("telemetry")
    if value is None:
        from .. import channel
        return channel.REPORTS_ON_BY_DEFAULT
    return bool(value)


def enabled(cfg: dict | None) -> bool:
    return available() and is_on(cfg) and bool((cfg or {}).get("install_id"))


def ensure_id(cfg: dict) -> bool:
    """Give this PC its random id. Returns True when the config changed."""
    if cfg.get("install_id"):
        return False
    cfg["install_id"] = uuid.uuid4().hex
    return True


def opt_in(cfg: dict):
    cfg["telemetry"] = True
    ensure_id(cfg)


def opt_out(cfg: dict):
    cfg["telemetry"] = False


def set_context(cfg: dict | None, version: str):
    _CTX["cfg"], _CTX["version"] = cfg, version


def locale_label() -> str:
    try:
        name = locale.getlocale()[0] or ""
    except ValueError:
        name = ""
    return (name or "unknown")[:20]


def cloud_label(sync_dir: str) -> str:
    """Which kind of cloud drive holds the shared folder - never the path."""
    try:
        from . import clouds
        low = str(sync_dir).lower()
        for label, root in clouds.detect_cloud_roots():
            if low.startswith(str(root).lower()):
                return label.lower()
    except Exception:
        pass
    return "other"


def send_crash(exc_type, tb):
    """Report an unhandled error by its type and the app function it hit."""
    where = "?"
    while tb is not None:
        code = tb.tb_frame.f_code
        if "app" in code.co_filename.replace("\\", "/").split("/"):
            where = code.co_name
        tb = tb.tb_next
    return send(_CTX["cfg"], "crash", None, _CTX["version"],
                kind=getattr(exc_type, "__name__", "Exception"), where=where)


def forget(cfg: dict) -> bool:
    """Erase every report this PC sent, then start over with a fresh random id."""
    install_id = cfg.get("install_id")
    ok = True
    if install_id and API_KEY:
        try:
            req = urllib.request.Request(
                FORGET_ENDPOINT, data=json.dumps({"p_install_id": install_id}).encode("utf-8"),
                method="POST", headers={"Content-Type": "application/json", "apikey": API_KEY,
                                        "Authorization": f"Bearer {API_KEY}",
                                        "User-Agent": "WorldSync"})
            urllib.request.urlopen(req, timeout=8).close()
        except Exception as e:
            log.warning("could not erase reports: %s", e)
            ok = False
    if ok:
        cfg["install_id"] = uuid.uuid4().hex
    return ok


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
        elif isinstance(value, bool):
            pass
        elif isinstance(value, (int, float)):
            value = round(value, 1) if isinstance(value, float) else value
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
    """Queue one report unless reports are switched off. Returns the payload (for tests)."""
    if event not in EVENTS or not enabled(cfg):
        return None
    payload = build_payload(cfg, event, game, version, **props)
    threading.Thread(target=_post, args=(payload,), daemon=True, name="report").start()
    return payload
