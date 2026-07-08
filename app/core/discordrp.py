"""Discord Rich Presence over the local IPC pipe — no dependency, no server.

Discord's desktop app listens on ``\\\\.\\pipe\\discord-ipc-0``; the protocol
is a 8-byte little-endian header (opcode, length) followed by JSON. Rich
Presence needs an application id the user creates for free at
discord.com/developers (Settings explains it). Everything fails soft: no
Discord, no id, no pipe — no problem.
"""

import json
import logging
import os
import struct
import uuid

log = logging.getLogger("dwsync.discordrp")

OP_HANDSHAKE = 0
OP_FRAME = 1
OP_CLOSE = 2


def encode_frame(opcode: int, payload: dict) -> bytes:
    data = json.dumps(payload).encode("utf-8")
    return struct.pack("<II", opcode, len(data)) + data


def activity_payload(pid: int, details: str, state: str, start: int | None) -> dict:
    activity = {"details": details[:120], "state": state[:120]}
    if start:
        activity["timestamps"] = {"start": int(start)}
    return {
        "cmd": "SET_ACTIVITY",
        "args": {"pid": pid, "activity": activity},
        "nonce": str(uuid.uuid4()),
    }


def clear_payload(pid: int) -> dict:
    return {"cmd": "SET_ACTIVITY", "args": {"pid": pid, "activity": None},
            "nonce": str(uuid.uuid4())}


class RichPresence:
    """Best-effort presence pusher. Every method swallows failure."""

    def __init__(self, app_id: str):
        self.app_id = (app_id or "").strip()
        self._pipe = None

    @property
    def available(self) -> bool:
        return bool(self.app_id) and os.name == "nt"

    def _connect(self) -> bool:
        if self._pipe is not None:
            return True
        if not self.available:
            return False
        for i in range(10):
            try:
                self._pipe = open(rf"\\.\pipe\discord-ipc-{i}", "r+b", buffering=0)
                self._pipe.write(encode_frame(OP_HANDSHAKE,
                                              {"v": 1, "client_id": self.app_id}))
                self._read_frame()   # handshake response
                log.info("Discord RP connected on pipe %d", i)
                return True
            except OSError:
                self._pipe = None
        return False

    def _read_frame(self):
        header = self._pipe.read(8)
        if len(header) < 8:
            raise OSError("short read")
        _op, length = struct.unpack("<II", header)
        return self._pipe.read(length)

    def set_playing(self, world_name: str, character: str = ""):
        import time
        try:
            if not self._connect():
                return
            details = f"In the wilds of {world_name}"
            state = f"as {character}" if character else "Shared world"
            self._pipe.write(encode_frame(
                OP_FRAME, activity_payload(os.getpid(), details, state,
                                           int(time.time()))))
            self._read_frame()
        except OSError:
            self.close()

    def clear(self):
        try:
            if self._pipe is not None:
                self._pipe.write(encode_frame(OP_FRAME, clear_payload(os.getpid())))
                self._read_frame()
        except OSError:
            pass
        finally:
            self.close()

    def close(self):
        try:
            if self._pipe is not None:
                self._pipe.close()
        except OSError:
            pass
        self._pipe = None
