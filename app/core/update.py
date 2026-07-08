"""In-app updates through the shared folder — no server, no store.

The host publishes a new build into an ``_app`` subfolder of any shared world
folder: the exe plus an ``update.json`` manifest. Everyone else's app notices
the higher version, downloads the exe (it's already syncing to their PC via
the cloud drive), and swaps itself on the next launch.

Because Windows won't let a running exe overwrite itself, ``apply_update``
stages the new exe and writes a tiny batch script that waits for this process
to exit, replaces the exe, and relaunches. All of that only runs from the
packaged exe; from source it's a no-op.
"""

import json
import logging
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from . import semver
from .storage import read_json, write_json

log = logging.getLogger("dwsync.update")

UPDATE_DIR_NAME = "_app"
UPDATE_MANIFEST = "update.json"


@dataclass
class UpdateInfo:
    version: str
    filename: str
    notes: str
    published_by: str
    exe_path: Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def current_exe() -> Path:
    return Path(sys.executable)


def publish(sync_dir, version: str, exe_source, published_by: str, notes: str = "") -> Path:
    """Copy this build into the shared folder so friends can auto-update.

    Returns the published manifest path. Used by a small 'Publish update'
    action the host runs after dropping in a new build.
    """
    import shutil

    update_dir = Path(sync_dir) / UPDATE_DIR_NAME
    update_dir.mkdir(parents=True, exist_ok=True)
    filename = f"DragonwildsSync-{version}.exe"
    shutil.copy2(exe_source, update_dir / filename)
    write_json(update_dir / UPDATE_MANIFEST, {
        "version": version,
        "filename": filename,
        "notes": notes,
        "published_by": published_by,
    })
    log.info("Published update v%s to %s", version, update_dir)
    return update_dir / UPDATE_MANIFEST


def check(sync_dir, current_version: str) -> UpdateInfo | None:
    """Return update info if the shared folder holds a newer, present build."""
    update_dir = Path(sync_dir) / UPDATE_DIR_NAME
    manifest = read_json(update_dir / UPDATE_MANIFEST)
    if not manifest:
        return None
    version = manifest.get("version", "")
    if not semver.is_newer(version, current_version):
        return None
    filename = manifest.get("filename", "")
    exe_path = update_dir / filename
    if not filename or not exe_path.exists():
        return None
    # Guard against a still-syncing partial download.
    try:
        if exe_path.stat().st_size < 1_000_000:
            return None
    except OSError:
        return None
    return UpdateInfo(
        version=version, filename=filename,
        notes=manifest.get("notes", ""),
        published_by=manifest.get("published_by", "a friend"),
        exe_path=exe_path,
    )


def build_swap_script(staged_exe: Path, target_exe: Path, script_path: Path) -> Path:
    """Write the batch script that swaps the exe after this process exits."""
    script = f"""@echo off
setlocal
echo Updating Dragonwilds Sync...
:waitloop
timeout /t 1 /nobreak >nul
copy /y "{staged_exe}" "{target_exe}" >nul 2>&1
if errorlevel 1 goto waitloop
start "" "{target_exe}"
del "{staged_exe}" >nul 2>&1
(goto) 2>nul & del "%~f0"
"""
    script_path.write_text(script, encoding="ascii")
    return script_path


def apply_update(info: UpdateInfo, staging_dir: Path) -> bool:
    """Stage the new exe and launch the swap script; caller should then quit.

    No-op (returns False) when running from source rather than the exe.
    """
    if not is_frozen():
        log.info("apply_update skipped: not running as a packaged exe")
        return False
    import shutil

    staging_dir.mkdir(parents=True, exist_ok=True)
    staged = staging_dir / info.filename
    shutil.copy2(info.exe_path, staged)
    script = build_swap_script(staged, current_exe(), staging_dir / "swap.bat")

    creationflags = 0
    if sys.platform == "win32":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | 0x00000008  # DETACHED_PROCESS
    subprocess.Popen(["cmd", "/c", str(script)], creationflags=creationflags,
                     close_fds=True)
    log.info("Update staged; swap script launched for v%s", info.version)
    return True
