"""Browsing and restoring the safety backups the sync core creates.

Backup folders are named ``YYYYmmdd-HHMMSS_<label>`` (see sync._backup_files).
Restore is deliberately local-only: it copies files back into the save folder
and lets the normal push flow (with all its conflict checks) share the result.
"""

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .sync import _backup_files

log = logging.getLogger("dwsync.backups")


@dataclass
class BackupInfo:
    path: Path
    stamp: datetime | None
    label: str          # e.g. "local_v13", "shared_v14", "pre_restore"
    file_count: int


def list_backups(backup_root) -> list[BackupInfo]:
    """Newest first. Unparseable folder names are shown, not hidden."""
    root = Path(backup_root)
    if not root.exists():
        return []
    infos = []
    for folder in sorted((p for p in root.iterdir() if p.is_dir()),
                         key=lambda p: p.name, reverse=True):
        name = folder.name
        stamp, label = None, name
        if "_" in name:
            raw, label = name.split("_", 1)
            try:
                stamp = datetime.strptime(raw, "%Y%m%d-%H%M%S")
            except ValueError:
                label = name
        files = [f for f in folder.iterdir() if f.is_file()]
        infos.append(BackupInfo(path=folder, stamp=stamp, label=label,
                                file_count=len(files)))
    return infos


def restore_backup(backup_path, save_dir, world_name: str, backup_root) -> int:
    """Copy a backup's files into the local save folder.

    The save files being replaced are themselves backed up first
    (label ``pre_restore``), so a restore is always reversible.
    Returns the number of files restored.
    """
    backup_path = Path(backup_path)
    save_dir = Path(save_dir)
    files = [f for f in backup_path.iterdir() if f.is_file()]
    if not files:
        return 0

    current = sorted(p for p in save_dir.glob(f"{world_name}*") if p.is_file()) \
        if save_dir.exists() else []
    if current:
        _backup_files(current, "pre_restore", backup_root)

    save_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, save_dir / f.name)
    log.info("Restored %d file(s) from %s", len(files), backup_path.name)
    return len(files)
