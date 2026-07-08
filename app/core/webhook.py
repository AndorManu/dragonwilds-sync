"""Generic webhook notifications: one URL field works for Discord, Slack,
ntfy.sh, or anything that accepts a plain POST.

Fire-and-forget: a webhook failure is logged and toasted at most — it can
never fail a sync.
"""

import json
import logging
import threading
import urllib.request

log = logging.getLogger("dwsync.webhook")

TIMEOUT_S = 8


def build_request(url: str, text: str) -> urllib.request.Request:
    """Shape the payload for the service the URL points at."""
    if "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        data = json.dumps({"content": text}).encode("utf-8")
        content_type = "application/json"
    elif "hooks.slack.com" in url:
        data = json.dumps({"text": text}).encode("utf-8")
        content_type = "application/json"
    else:  # ntfy.sh and friends: plain body
        data = text.encode("utf-8")
        content_type = "text/plain; charset=utf-8"
    return urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": content_type, "User-Agent": "DragonwildsSync"},
    )


def send_async(url: str, text: str, on_error=None):
    """POST in a background thread; never raises into the caller."""
    if not url:
        return

    def worker():
        try:
            with urllib.request.urlopen(build_request(url, text), timeout=TIMEOUT_S) as resp:
                log.info("Webhook delivered (%s)", resp.status)
        except Exception as e:
            log.warning("Webhook failed: %s", e)
            if on_error:
                on_error(str(e))

    threading.Thread(target=worker, daemon=True, name="webhook").start()
