"""Group-level world history: keep the last few shared versions in the cloud.

Local backups only save whoever made them. Archiving each pushed version
into ``_history/v{n}/`` inside the shared folder gives the *whole group* a
rollback path. Pruned to a small number so cloud quota stays polite.
Everything here is additive and fail-soft — it runs after the frozen sync
core has already succeeded, and can never affect a push.
"""

import logging
import re
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .sync import world_files

log = logging.getLogger("dwsync.worldhistory")

HISTORY_DIRNAME = "_history"
VERSIONS_TO_KEEP = 3


@dataclass
class ArchivedVersion:
    version: int
    path: Path
    modified: datetime | None
    total_bytes: int
    file_count: int


def _history_root(sync_dir) -> Path:
    return Path(sync_dir) / HISTORY_DIRNAME


def archive_version(sync_dir, world_name: str, version: int,
                    keep: int = VERSIONS_TO_KEEP) -> bool:
    """Copy the just-pushed world files into _history/v{version}; prune."""
    try:
        files = world_files(Path(sync_dir), world_name)
        if not files:
            return False
        dest = _history_root(sync_dir) / f"v{version}"
        dest.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, dest / f.name)
        _prune(sync_dir, keep)
        log.info("Archived v%d to group history", version)
        return True
    except OSError:
        log.warning("Could not archive world version", exc_info=True)
        return False


def _prune(sync_dir, keep: int):
    root = _history_root(sync_dir)
    if not root.exists():
        return
    versions = []
    for p in root.iterdir():
        m = re.fullmatch(r"v(\d+)", p.name)
        if p.is_dir() and m:
            versions.append((int(m.group(1)), p))
    versions.sort(reverse=True)
    for _, path in versions[keep:]:
        shutil.rmtree(path, ignore_errors=True)


def list_versions(sync_dir) -> list[ArchivedVersion]:
    """Newest first."""
    root = _history_root(sync_dir)
    if not root.exists():
        return []
    out = []
    for p in root.iterdir():
        m = re.fullmatch(r"v(\d+)", p.name)
        if not (p.is_dir() and m):
            continue
        files = [f for f in p.iterdir() if f.is_file()]
        try:
            modified = datetime.fromtimestamp(max(f.stat().st_mtime for f in files)) \
                if files else None
        except OSError:
            modified = None
        out.append(ArchivedVersion(
            version=int(m.group(1)), path=p, modified=modified,
            total_bytes=sum(f.stat().st_size for f in files),
            file_count=len(files)))
    out.sort(key=lambda v: v.version, reverse=True)
    return out
