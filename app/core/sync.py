"""Core save-relay logic: pull / push / versioning / conflict detection.

Ported faithfully from the validated prototype (dragonwilds_sync.py). The
protocol is unchanged:

- The shared folder holds the world files plus a ``version.json`` manifest:
  ``{version, last_editor, timestamp, world_name}``. Every push bumps
  ``version`` by 1 and rewrites the manifest.
- Local state tracks ``{last_applied_version, last_hash}`` — the last version
  this machine pulled/pushed and the hash of the primary save file then.
- Pull: if shared version > last_applied_version, copy ``{world_name}*`` from
  the shared folder into the local save folder. If the local save's current
  hash differs from ``last_hash`` (played without pushing), require explicit
  confirmation before overwriting.
- Push: copy ``{world_name}*`` into the shared folder, bump the version,
  rewrite the manifest, update local state.

Additions on top of the prototype (protocol-compatible):

- The manifest also carries a capped ``history`` list of past sessions, which
  powers the activity feed. Old manifests without it keep working.
- Push now mirrors pull's conflict check: if the shared version moved past
  our ``last_applied_version`` (someone pushed while we played), confirmation
  is required before overwriting their session.
- Before any overwrite (either direction) the files being replaced are copied
  to a local backups folder, pruned to the most recent few.

All functions are UI-agnostic: they take ``log(message)`` and
``confirm(title, body) -> bool`` callbacks and never touch global paths, so
the exact same code runs under pytest and behind the GUI.
"""

import hashlib
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum, auto
from pathlib import Path

from . import paths
from .storage import read_json, write_json

logger = logging.getLogger("dwsync.sync")

HISTORY_LIMIT = 50
BACKUPS_TO_KEEP = 10

# Bumped only when the manifest layout changes incompatibly. Written on push
# so older apps can be warned instead of failing in confusing ways.
MANIFEST_SCHEMA = 1

# Optional per-entry annotations added after a push (session notes, duration,
# flair, which character was played and how they look). Amending these never
# touches save files or the version counter.
AMENDABLE_FIELDS = {"note", "duration_s", "emoji", "color", "character", "portrait"}


class SyncResult(Enum):
    PULLED = auto()
    UP_TO_DATE = auto()
    NO_SHARED = auto()          # no manifest in the shared folder yet
    MISSING_FILES = auto()      # manifest exists but the save files don't
    CONFLICT_CANCELLED = auto() # user chose to keep local, un-pushed progress
    PUSHED = auto()
    NOTHING_TO_PUSH = auto()    # no local files matching the world name
    STALE_CANCELLED = auto()    # user chose not to overwrite a newer shared save


@dataclass
class StatusSnapshot:
    """A read-only view of where this machine stands vs. the shared folder."""
    kind: str                 # no_shared | behind | up_to_date | folder_missing
    local_version: int
    shared_version: int | None = None
    last_editor: str | None = None
    timestamp: str | None = None
    history: list | None = None
    manifest_schema: int | None = None  # for newer-app warnings; None on old manifests


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def world_files(folder: Path, world_name: str) -> list[Path]:
    """Every file in `folder` that belongs to this world (save + backup)."""
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob(f"{world_name}*") if p.is_file())


def get_shared_manifest(sync_dir: Path):
    return read_json(Path(sync_dir) / paths.MANIFEST_NAME)


def get_status(cfg, state) -> StatusSnapshot:
    sync_dir = Path(cfg["sync_dir"])
    local_version = state.get("last_applied_version", 0)
    if not sync_dir.exists():
        return StatusSnapshot(kind="folder_missing", local_version=local_version)
    manifest = get_shared_manifest(sync_dir)
    if not manifest:
        return StatusSnapshot(kind="no_shared", local_version=local_version)
    kind = "behind" if manifest["version"] > local_version else "up_to_date"
    return StatusSnapshot(
        kind=kind,
        local_version=local_version,
        shared_version=manifest["version"],
        last_editor=manifest.get("last_editor"),
        timestamp=manifest.get("timestamp"),
        history=manifest.get("history"),
        manifest_schema=manifest.get("app_schema"),
    )


def _backup_files(files: list[Path], label: str, backup_root: Path):
    """Copy `files` into a timestamped backup folder; prune old backups."""
    if not files:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = Path(backup_root) / f"{stamp}_{label}"
    dest.mkdir(parents=True, exist_ok=True)
    for f in files:
        shutil.copy2(f, dest / f.name)
    # Keep only the newest few backup folders.
    folders = sorted(
        (p for p in Path(backup_root).iterdir() if p.is_dir()),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in folders[BACKUPS_TO_KEEP:]:
        shutil.rmtree(old, ignore_errors=True)
    logger.info("Backed up %d file(s) to %s", len(files), dest)
    return dest


def do_pull(cfg, state, log, confirm, backup_root: Path = paths.BACKUP_DIR):
    """Bring the local save up to the shared version.

    Returns (SyncResult, state). `state` is updated in place on success.
    """
    sync_dir = Path(cfg["sync_dir"])
    save_dir = Path(cfg["local_save_dir"])
    world_name = cfg["world_name"]
    manifest = get_shared_manifest(sync_dir)

    if not manifest:
        log("No shared save yet — you'll be the first to share one after this session.")
        return SyncResult.NO_SHARED, state

    shared_version = manifest["version"]
    if shared_version <= state.get("last_applied_version", 0):
        log(f"Already up to date (v{shared_version}).")
        return SyncResult.UP_TO_DATE, state

    # Conflict check: the local save changed since our last known sync point
    # but was never pushed (e.g. played without the app / offline).
    local_files = world_files(save_dir, world_name)
    if local_files and state.get("last_hash"):
        current_hash = sha256_file(local_files[0])
        if current_hash != state["last_hash"]:
            proceed = confirm(
                "Overwrite your local progress?",
                f"Your local save has changed since your last sync, but a newer "
                f"save (v{shared_version}, from {manifest.get('last_editor', 'a friend')}) "
                f"is waiting in the shared folder.\n\n"
                f"Continuing will replace your local, un-shared progress.",
            )
            if not proceed:
                log("Kept your local progress. Use “Save my progress now” first if you want to share it.")
                return SyncResult.CONFLICT_CANCELLED, state

    shared_files = world_files(sync_dir, world_name)
    if not shared_files:
        log("A newer save is listed, but its files haven't appeared in the shared folder yet. "
            "Give your cloud folder a moment to finish syncing, then try again.")
        return SyncResult.MISSING_FILES, state

    # Safety net: keep a local copy of whatever we're about to overwrite.
    if local_files:
        _backup_files(local_files, f"local_v{state.get('last_applied_version', 0)}", backup_root)

    save_dir.mkdir(parents=True, exist_ok=True)
    for f in shared_files:
        shutil.copy2(f, save_dir / f.name)

    state["last_applied_version"] = shared_version
    state["last_hash"] = sha256_file(save_dir / shared_files[0].name)
    log(f"Got the latest world — v{shared_version}, last played by {manifest.get('last_editor', 'a friend')}.")
    return SyncResult.PULLED, state


def do_push(cfg, state, log, confirm, backup_root: Path = paths.BACKUP_DIR):
    """Publish the local save to the shared folder and bump the version.

    Returns (SyncResult, state). `state` is updated in place on success.
    """
    sync_dir = Path(cfg["sync_dir"])
    save_dir = Path(cfg["local_save_dir"])
    world_name = cfg["world_name"]

    local_files = world_files(save_dir, world_name)
    if not local_files:
        log(f"No save files found for “{world_name}” — nothing to share yet.")
        return SyncResult.NOTHING_TO_PUSH, state

    manifest = get_shared_manifest(sync_dir)

    # Mirror of the pull-side conflict check: someone pushed while we played.
    last_applied = state.get("last_applied_version", 0)
    if manifest and manifest["version"] > last_applied:
        proceed = confirm(
            "Someone else saved while you were playing",
            f"{manifest.get('last_editor', 'A friend')} shared v{manifest['version']} "
            f"after you last synced (you're on v{last_applied}).\n\n"
            f"Sharing now will replace their session with yours.",
        )
        if not proceed:
            log("Didn't share. Your progress is still on this machine — hit Play to sync up first.")
            return SyncResult.STALE_CANCELLED, state
        _backup_files(
            world_files(sync_dir, world_name),
            f"shared_v{manifest['version']}", backup_root,
        )

    # Version base survives a corrupted/deleted manifest: never go backwards.
    base = manifest["version"] if manifest else 0
    new_version = max(base, last_applied) + 1

    sync_dir.mkdir(parents=True, exist_ok=True)
    for f in local_files:
        shutil.copy2(f, sync_dir / f.name)

    entry = {
        "version": new_version,
        "editor": cfg["player_name"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    history = (manifest.get("history", []) if manifest else [])
    history = (history + [entry])[-HISTORY_LIMIT:]

    write_json(Path(sync_dir) / paths.MANIFEST_NAME, {
        "version": new_version,
        "last_editor": cfg["player_name"],
        "timestamp": entry["timestamp"],
        "world_name": world_name,
        "history": history,
        "app_schema": MANIFEST_SCHEMA,
    })

    state["last_applied_version"] = new_version
    state["last_hash"] = sha256_file(local_files[0])
    log(f"Shared your progress as v{new_version}. Friends will get it next time they hit Play.")
    return SyncResult.PUSHED, state


def amend_history_entry(sync_dir, version: int, **fields) -> bool:
    """Annotate an already-pushed history entry (session note, duration, flair).

    Strictly additive metadata: only whitelisted fields, only on the matching
    version's history entry. Never touches save files, the version counter,
    or any other manifest field, so it cannot affect sync correctness.
    """
    allowed = {k: v for k, v in fields.items()
               if k in AMENDABLE_FIELDS and v not in (None, "")}
    if not allowed:
        return False
    manifest = get_shared_manifest(sync_dir)
    if not manifest:
        return False
    changed = False
    for entry in manifest.get("history", []):
        if entry.get("version") == version:
            entry.update(allowed)
            changed = True
    if changed:
        write_json(Path(sync_dir) / paths.MANIFEST_NAME, manifest)
    return changed
