"""Detecting cloud-drive folders on this machine, and watching for a shared
folder to appear after a friend accepts an invite."""

import os
import string
from pathlib import Path

from . import paths
from .storage import read_json

GOOGLE_DRIVE_DOWNLOAD_URL = "https://www.google.com/drive/download/"


def detect_cloud_roots() -> list[tuple[str, Path]]:
    """(label, root) for every cloud-synced folder we can find."""
    roots: list[tuple[str, Path]] = []
    onedrive = os.environ.get("OneDrive") or os.environ.get("OneDriveConsumer")
    if onedrive and Path(onedrive).exists():
        roots.append(("OneDrive", Path(onedrive)))
    dropbox = Path.home() / "Dropbox"
    if dropbox.exists():
        roots.append(("Dropbox", dropbox))
    gd_home = Path.home() / "Google Drive"
    if gd_home.exists():
        roots.append(("Google Drive", gd_home))
    for letter in string.ascii_uppercase:
        candidate = Path(f"{letter}:/My Drive")
        try:
            if candidate.exists():
                roots.append(("Google Drive", candidate))
        except OSError:
            continue
    return roots


def google_drive_present() -> bool:
    return any(label == "Google Drive" for label, _ in detect_cloud_roots())


def any_cloud_present() -> bool:
    return bool(detect_cloud_roots())


def find_synced_folder(folder_name: str, world_name: str | None = None) -> Path | None:
    """Look for `folder_name` at the top of every cloud root.

    If a manifest is present it must be for `world_name`; a folder without a
    manifest still matches (brand-new world, nothing pushed yet).
    """
    for _, root in detect_cloud_roots():
        candidate = root / folder_name
        try:
            if not candidate.is_dir():
                continue
        except OSError:
            continue
        if world_name:
            manifest = read_json(candidate / paths.MANIFEST_NAME)
            if manifest and manifest.get("world_name") not in (None, world_name):
                continue
        return candidate
    return None
