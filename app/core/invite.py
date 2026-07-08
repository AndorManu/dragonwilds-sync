"""Invite codes: everything a friend needs to join a world, in one string.

Fully local — the code is just compressed JSON (world name, shared folder
name, optional cloud share link), base64url-encoded with a versioned prefix.
No backend anywhere: the cloud drive itself is the transport.
"""

import base64
import json
import zlib

PREFIX = "DWS1."
MAX_CODE_LEN = 2000


class InviteError(ValueError):
    """Raised when a code can't be decoded; message is user-friendly."""


def encode(world_name: str, folder_name: str, share_link: str | None) -> str:
    payload = {"v": 1, "w": world_name, "f": folder_name, "l": share_link or ""}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    packed = base64.urlsafe_b64encode(zlib.compress(raw, 9)).decode("ascii").rstrip("=")
    return PREFIX + packed


def decode(code: str) -> dict:
    """Returns {world_name, folder_name, share_link}. Raises InviteError."""
    code = "".join((code or "").split())  # tolerate whitespace/newlines from chat apps
    if not code:
        raise InviteError("That looks empty — paste the whole invite code.")
    if len(code) > MAX_CODE_LEN:
        raise InviteError("That's too long to be an invite code.")
    if not code.startswith(PREFIX):
        raise InviteError("That doesn't look like a Dragonwilds Sync invite code.")
    packed = code[len(PREFIX):]
    try:
        padded = packed + "=" * (-len(packed) % 4)
        raw = zlib.decompress(base64.urlsafe_b64decode(padded))
        payload = json.loads(raw)
    except Exception:
        raise InviteError("That code is damaged — ask your friend to send it again.")
    if payload.get("v") != 1 or not payload.get("w") or not payload.get("f"):
        raise InviteError("That code is from an unsupported version — "
                          "ask your friend to update their app.")
    return {
        "world_name": str(payload["w"]),
        "folder_name": str(payload["f"]),
        "share_link": str(payload.get("l") or "") or None,
    }
