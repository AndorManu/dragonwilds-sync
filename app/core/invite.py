"""Invite codes: everything a friend needs to join a world, in one string.

Fully local - the code is just compressed JSON (world name, shared folder
name, optional cloud share link), base64url-encoded with a versioned prefix.
No backend anywhere: the cloud drive itself is the transport.

Two prefixes: ``DWS1.`` is the original Dragonwilds Sync format and is still
written for Dragonwilds worlds, so friends on 1.x can join. Every other game
uses ``WS1.`` with the game id inside; 1.x apps reject those cleanly instead
of copying the wrong game's files.
"""

import base64
import json
import zlib

PREFIX = "WS1."
LEGACY_PREFIX = "DWS1."
LEGACY_GAME = "dragonwilds"
MAX_CODE_LEN = 2000


class InviteError(ValueError):
    """Raised when a code can't be decoded; message is user-friendly."""


def encode(world_name: str, folder_name: str, share_link: str | None,
           game: str = LEGACY_GAME, label: str | None = None) -> str:
    payload = {"v": 1, "w": world_name, "f": folder_name, "l": share_link or ""}
    prefix = LEGACY_PREFIX
    if game != LEGACY_GAME:
        payload["g"] = game
        prefix = PREFIX
        if label and label != world_name:
            payload["n"] = label
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    packed = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return prefix + packed


def decode(code: str) -> dict:
    """Returns {world_name, folder_name, share_link, game}. Raises InviteError."""
    code = "".join((code or "").split())  # tolerate whitespace/newlines from chat apps
    if not code:
        raise InviteError("That looks empty - paste the whole invite code.")
    if len(code) > MAX_CODE_LEN:
        raise InviteError("That's too long to be an invite code.")
    if code.startswith(LEGACY_PREFIX):
        packed = code[len(LEGACY_PREFIX):]
    elif code.startswith(PREFIX):
        packed = code[len(PREFIX):]
    else:
        raise InviteError("That doesn't look like a WorldSync invite code.")
    try:
        padded = packed + "=" * (-len(packed) % 4)
        raw = zlib.decompress(base64.urlsafe_b64decode(padded))
        payload = json.loads(raw)
    except Exception:
        raise InviteError("That code is damaged - ask your friend to send it again.")
    if payload.get("v") != 1 or not payload.get("w") or not payload.get("f"):
        raise InviteError("That code is from an unsupported version - "
                          "ask your friend to update their app.")
    return {
        "world_name": str(payload["w"]),
        "folder_name": str(payload["f"]),
        "share_link": str(payload.get("l") or "") or None,
        "game": str(payload.get("g") or LEGACY_GAME),
        "label": str(payload.get("n") or "") or None,
    }
