"""Core save-relay logic: pull / push / versioning / conflict detection.

Ported faithfully from the validated prototype (dragonwilds_sync.py). The
protocol is unchanged:

- The shared folder holds the world files plus a ``version.json`` manifest:
  ``{version, last_editor, timestamp, world_name}``. Every push bumps
  ``version`` by 1 and rewrites the manifest.
- Local state tracks ``{last_applied_version, last_hash}`` - the last version
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

import glob as _glob
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
    WRONG_GAME = auto()         # the shared folder holds a different game's world


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


def world_files(folder: Path, world_name: str, patterns=None) -> list[Path]:
    """Every file in `folder` that belongs to this world.

    ``patterns=None`` is the original rule (top-level files whose name starts
    with the world name), kept exactly for Dragonwilds groups. Otherwise each
    pattern is a glob relative to `folder` with ``{world}`` / ``{map}``
    placeholders, and matches may sit in subfolders.
    """
    folder = Path(folder)
    if not folder.exists():
        return []
    if patterns is None:
        return sorted(p for p in folder.glob(f"{world_name}*") if p.is_file())
    if not world_name:
        return []           # an empty id would turn "{world}/**/*" into the whole drive
    safe = _glob.escape(world_name)
    first = _glob.escape(world_name.split("/", 1)[0])
    found = {}
    for pattern in patterns:
        try:
            matches = folder.glob(pattern.format(world=safe, map=first))
            for p in matches:
                if p.is_file():
                    found[p.relative_to(folder).as_posix()] = p
        except (OSError, ValueError, NotImplementedError):
            continue
    return [found[k] for k in sorted(found)]


def _rel(path: Path, root: Path) -> Path:
    try:
        return Path(path).relative_to(root)
    except ValueError:
        return Path(Path(path).name)


def world_fingerprint(files: list[Path], root: Path, patterns=None) -> str | None:
    """What "this save changed" is measured against.

    Legacy worlds hash the first file (the protocol v1 always used). Folder
    worlds hash every file plus its relative path, so a new autosave or a
    deleted one counts as a change too.
    """
    if not files:
        return None
    if patterns is None:
        return sha256_file(files[0])
    h = hashlib.sha256()
    for f in files:
        h.update(_rel(f, root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(sha256_file(f).encode("ascii"))
    return h.hexdigest()


def _copy_world(files: list[Path], src_root: Path, dst_root: Path):
    for f in files:
        dest = Path(dst_root) / _rel(f, src_root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dest)


def _remove_stale(dst_root: Path, world_name: str, patterns, keep: set[str]):
    """Mirror mode: drop world files the source side no longer has."""
    for f in world_files(dst_root, world_name, patterns):
        if _rel(f, dst_root).as_posix() not in keep:
            try:
                f.unlink()
            except OSError:
                logger.warning("Could not remove stale file %s", f)


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


def _backup_files(files: list[Path], label: str, backup_root: Path, root: Path | None = None):
    """Copy `files` into a timestamped backup folder; prune old backups.

    With `root`, files keep their path relative to it (folder worlds);
    without, they're stored flat by name as before.
    """
    if not files:
        return None
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest, n = Path(backup_root) / f"{stamp}_{label}", 2
    while dest.exists():          # avoid same-second collisions losing a backup
        dest = Path(backup_root) / f"{stamp}_{label}-{n}"
        n += 1
    dest.mkdir(parents=True)
    for f in files:
        target = dest / (_rel(f, root) if root is not None else Path(f).name)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
    # Keep only the newest few backup folders.
    folders = sorted(
        (p for p in Path(backup_root).iterdir() if p.is_dir() and p.name != "checkpoints"),
        key=lambda p: p.name,
        reverse=True,
    )
    for old in folders[BACKUPS_TO_KEEP:]:
        shutil.rmtree(old, ignore_errors=True)
    logger.info("Backed up %d file(s) to %s", len(files), dest)
    return dest


def _world_spec(cfg):
    """(save_dir, world_name, patterns, mirror, game) from a flat cfg."""
    patterns = cfg.get("patterns")
    return (Path(cfg["local_save_dir"]), cfg["world_name"],
            list(patterns) if patterns is not None else None,
            bool(cfg.get("mirror")), cfg.get("game"))


def _wrong_game(manifest, game) -> bool:
    """True if the shared folder was made for a different game.

    Manifests from before WorldSync carry no game and are Dragonwilds; a
    flat cfg without a game (tests, characters) skips the check.
    """
    if not manifest or not game:
        return False
    return manifest.get("game", "dragonwilds") != game


def do_pull(cfg, state, log, confirm, backup_root: Path = paths.BACKUP_DIR):
    """Bring the local save up to the shared version.

    Returns (SyncResult, state). `state` is updated in place on success.
    """
    sync_dir = Path(cfg["sync_dir"])
    save_dir, world_name, patterns, mirror, game = _world_spec(cfg)
    manifest = get_shared_manifest(sync_dir)

    if not manifest:
        log("No shared save yet - you'll be the first to share one after this session.")
        return SyncResult.NO_SHARED, state

    if _wrong_game(manifest, game):
        log(f"The shared folder holds a {manifest.get('game', 'dragonwilds')} world, "
            f"not {game}. Nothing was copied.")
        return SyncResult.WRONG_GAME, state

    shared_version = manifest["version"]
    if shared_version <= state.get("last_applied_version", 0):
        log(f"Already up to date (v{shared_version}).")
        return SyncResult.UP_TO_DATE, state

    # Conflict check: the local save changed since our last known sync point
    # but was never pushed (e.g. played without the app / offline).
    local_files = world_files(save_dir, world_name, patterns)
    if local_files and state.get("last_hash"):
        current_hash = world_fingerprint(local_files, save_dir, patterns)
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

    shared_files = world_files(sync_dir, world_name, patterns)
    if not shared_files:
        log("A newer save is listed, but its files haven't appeared in the shared folder yet. "
            "Give your cloud folder a moment to finish syncing, then try again.")
        return SyncResult.MISSING_FILES, state

    # Safety net: keep a local copy of whatever we're about to overwrite.
    if local_files:
        _backup_files(local_files, f"local_v{state.get('last_applied_version', 0)}", backup_root,
                      root=save_dir if patterns is not None else None)

    save_dir.mkdir(parents=True, exist_ok=True)
    _copy_world(shared_files, sync_dir, save_dir)
    if mirror:
        _remove_stale(save_dir, world_name, patterns,
                      {_rel(f, sync_dir).as_posix() for f in shared_files})

    state["last_applied_version"] = shared_version
    state["last_hash"] = world_fingerprint(
        world_files(save_dir, world_name, patterns), save_dir, patterns)
    log(f"Got the latest world - v{shared_version}, last played by {manifest.get('last_editor', 'a friend')}.")
    return SyncResult.PULLED, state


def do_push(cfg, state, log, confirm, backup_root: Path = paths.BACKUP_DIR):
    """Publish the local save to the shared folder and bump the version.

    Returns (SyncResult, state). `state` is updated in place on success.
    """
    sync_dir = Path(cfg["sync_dir"])
    save_dir, world_name, patterns, mirror, game = _world_spec(cfg)

    local_files = world_files(save_dir, world_name, patterns)
    if not local_files:
        log(f"No save files found for “{world_name}” - nothing to share yet.")
        return SyncResult.NOTHING_TO_PUSH, state

    manifest = get_shared_manifest(sync_dir)
    if _wrong_game(manifest, game):
        log(f"The shared folder holds a {manifest.get('game', 'dragonwilds')} world, "
            f"not {game}. Nothing was shared.")
        return SyncResult.WRONG_GAME, state

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
            log("Didn't share. Your progress is still on this machine - hit Play to sync up first.")
            return SyncResult.STALE_CANCELLED, state
        _backup_files(
            world_files(sync_dir, world_name, patterns),
            f"shared_v{manifest['version']}", backup_root,
            root=sync_dir if patterns is not None else None,
        )

    # Version base survives a corrupted/deleted manifest: never go backwards.
    base = manifest["version"] if manifest else 0
    new_version = max(base, last_applied) + 1

    sync_dir.mkdir(parents=True, exist_ok=True)
    _copy_world(local_files, save_dir, sync_dir)
    if mirror:
        _remove_stale(sync_dir, world_name, patterns,
                      {_rel(f, save_dir).as_posix() for f in local_files})

    entry = {
        "version": new_version,
        "editor": cfg["player_name"],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    history = (manifest.get("history", []) if manifest else [])
    history = (history + [entry])[-HISTORY_LIMIT:]

    new_manifest = {
        "version": new_version,
        "last_editor": cfg["player_name"],
        "timestamp": entry["timestamp"],
        "world_name": world_name,
        "history": history,
        "app_schema": MANIFEST_SCHEMA,
    }
    if game:
        new_manifest["game"] = game
    write_json(Path(sync_dir) / paths.MANIFEST_NAME, new_manifest)

    state["last_applied_version"] = new_version
    state["last_hash"] = world_fingerprint(local_files, save_dir, patterns)
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
