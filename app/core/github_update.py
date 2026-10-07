"""Updates straight from the GitHub releases page.

Every few hours the packaged app asks GitHub for the latest release. If it is
newer, the matching exe (WorldSync.exe, or WorldSync-Nexus.exe for the Nexus
build) is downloaded in the background, checked against the size and SHA-256
GitHub publishes for it, and then offered through the same "Update & restart"
bar as a friend's update. Nothing is installed without the player clicking.

The request goes to api.github.com and carries no id; GitHub sees an IP like
for any download. Switched off with one checkbox in Settings.
"""

import hashlib
import json
import logging
import os
import time
import urllib.request
from pathlib import Path

from . import semver
from .update import UpdateInfo

log = logging.getLogger("dwsync.update")

REPO = "AndorManu/worldsync"
API_LATEST = f"https://api.github.com/repos/{REPO}/releases/latest"
CHECK_EVERY_S = 6 * 3600
TIMEOUT_S = 10
MIN_EXE_BYTES = 1_000_000
PUBLISHER = "WorldSync on GitHub"


def asset_name() -> str:
    from .. import channel
    return "WorldSync-Nexus.exe" if channel.CHANNEL == "nexus" else "WorldSync.exe"


def _get_json(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json", "User-Agent": "WorldSync"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _notes(body: str) -> str:
    """The first real line of the release notes, for the update prompt."""
    for line in (body or "").splitlines():
        line = line.strip().lstrip("#-* ").strip()
        if line and "http" not in line and "Full Changelog" not in line:
            return line[:200]
    return ""


def latest_release(current_version: str, fetch=_get_json) -> dict | None:
    """The newer release's exe as {version, url, size, sha256, notes}, or None."""
    data = fetch(API_LATEST)
    if not isinstance(data, dict) or data.get("draft") or data.get("prerelease"):
        return None
    version = str(data.get("tag_name") or "").lstrip("v")
    if not semver.is_newer(version, current_version):
        return None
    want = asset_name()
    for asset in data.get("assets") or []:
        if asset.get("name") == want:
            digest = str(asset.get("digest") or "")
            return {
                "version": version,
                "url": asset.get("browser_download_url") or "",
                "size": int(asset.get("size") or 0),
                "sha256": digest[7:].lower() if digest.startswith("sha256:") else "",
                "notes": _notes(data.get("body") or ""),
            }
    return None


def _download(url: str, dest: Path, opener=urllib.request.urlopen) -> str:
    """Stream `url` into `dest`, returning the SHA-256 of what was written."""
    sha = hashlib.sha256()
    req = urllib.request.Request(url, headers={"User-Agent": "WorldSync"})
    with opener(req, timeout=60) as resp, open(dest, "wb") as out:
        while True:
            chunk = resp.read(1 << 16)
            if not chunk:
                break
            sha.update(chunk)
            out.write(chunk)
    return sha.hexdigest()


def fetch_update(release: dict, folder: Path, download=_download) -> UpdateInfo | None:
    """Download and verify the release exe; an UpdateInfo ready to apply, or None."""
    if not release.get("url"):
        return None
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"WorldSync-{release['version']}.exe"
    final = folder / filename
    part = folder / (filename + ".part")
    if final.exists() and final.stat().st_size == release["size"]:
        log.info("Update v%s already downloaded", release["version"])
    else:
        digest = download(release["url"], part)
        size = part.stat().st_size
        if size < MIN_EXE_BYTES or (release["size"] and size != release["size"]):
            log.warning("Update download has the wrong size (%s bytes); dropped", size)
            part.unlink(missing_ok=True)
            return None
        if release["sha256"] and digest != release["sha256"]:
            log.warning("Update download failed its SHA-256 check; dropped")
            part.unlink(missing_ok=True)
            return None
        os.replace(part, final)
    return UpdateInfo(version=release["version"], filename=filename,
                      notes=release.get("notes", ""), published_by=PUBLISHER,
                      exe_path=final)


class Checker:
    """Remembers when GitHub was last asked, so the poll loop can call it freely."""

    def __init__(self, every_s: float = CHECK_EVERY_S, clock=time.monotonic):
        self.every_s, self.clock, self._last = every_s, clock, None

    def due(self) -> bool:
        return self._last is None or self.clock() - self._last >= self.every_s

    def check(self, current_version: str, folder: Path) -> UpdateInfo | None:
        self._last = self.clock()
        release = latest_release(current_version)
        if not release:
            return None
        return fetch_update(release, folder)
