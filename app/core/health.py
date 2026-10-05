"""Save-file health and cloud-sync-state checks.

These run in the controller *around* the frozen sync core - never inside it -
so they can't affect the validated push/pull logic. They exist to catch the
two failure modes the raw protocol can't see:

- pushing a corrupt / zero-byte save that would poison the group, and
- pulling from a shared folder that's still mid-download (partial files).
"""

from dataclasses import dataclass
from pathlib import Path

from .sync import world_files

# A real Dragonwilds .sav is comfortably larger than this; below it, assume
# the file is truncated / not yet written.
MIN_HEALTHY_SAVE = 1024

# Extensions cloud clients use for in-progress downloads.
PARTIAL_SUFFIXES = (".tmp", ".crdownload", ".partial", ".gdownload",
                    ".download", ".!qb", ".part")


@dataclass
class SaveHealth:
    ok: bool
    reason: str = ""
    primary_size: int = 0


def _primary(files: list[Path], patterns) -> Path:
    """The file that best represents the save: the .sav for Dragonwilds,
    otherwise the biggest file (the world data, not an index or thumbnail)."""
    if patterns is None:
        return next((f for f in files if f.suffix.lower() == ".sav"), files[0])
    sized = []
    for f in files:
        try:
            sized.append((f.stat().st_size, f))
        except OSError:
            continue
    return max(sized, key=lambda t: t[0])[1] if sized else files[0]


def check_local_save(save_dir, world_name: str, patterns=None) -> SaveHealth:
    """Is there a plausibly-complete local save worth sharing?"""
    files = world_files(Path(save_dir), world_name, patterns)
    if not files:
        return SaveHealth(False, "no save files found")
    primary = _primary(files, patterns)
    try:
        size = primary.stat().st_size
    except OSError:
        return SaveHealth(False, "couldn't read the save file")
    if size < MIN_HEALTHY_SAVE:
        return SaveHealth(False, "the save file looks empty or truncated", size)
    return SaveHealth(True, "", size)


def shared_still_syncing(sync_dir, world_name: str, patterns=None) -> bool:
    """True if the shared folder shows signs of an in-progress cloud download."""
    folder = Path(sync_dir)
    if not folder.exists():
        return False
    for p in folder.iterdir():
        try:
            name = p.name.lower()
            if any(name.endswith(sfx) for sfx in PARTIAL_SUFFIXES):
                return True
        except OSError:
            continue
    files = world_files(folder, world_name, patterns)
    if patterns is not None:
        # folder worlds: a partial download can sit deep inside the world
        if any(f.name.lower().endswith(PARTIAL_SUFFIXES) for f in files):
            return True
        if files:
            try:
                return _primary(files, patterns).stat().st_size == 0
            except OSError:
                return False
        return False
    # A world file that exists but is zero bytes is a classic half-synced state.
    for f in files:
        try:
            if f.suffix.lower() == ".sav" and f.stat().st_size == 0:
                return True
        except OSError:
            continue
    return False
