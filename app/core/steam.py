"""Finding the game install via the Steam registry + library folders."""

import logging
import re
from pathlib import Path

from . import games

log = logging.getLogger("dwsync.steam")

try:
    import winreg
except ImportError:  # non-Windows dev environments
    winreg = None


def _steam_root() -> Path | None:
    if not winreg:
        return None
    for hive, key in (
        (winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Valve\Steam"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Valve\Steam"),
    ):
        try:
            with winreg.OpenKey(hive, key) as k:
                value, _ = winreg.QueryValueEx(
                    k, "SteamPath" if hive == winreg.HKEY_CURRENT_USER else "InstallPath")
                root = Path(value)
                if root.exists():
                    return root
        except OSError:
            continue
    return None


def _library_folders(steam_root: Path) -> list[Path]:
    libraries = [steam_root]
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        text = vdf.read_text(encoding="utf-8", errors="replace")
        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            p = Path(match.group(1).replace("\\\\", "\\"))
            if p.exists():
                libraries.append(p)
    except OSError:
        pass
    return libraries


def _libraries() -> list[Path]:
    root = _steam_root()
    return _library_folders(root) if root else []


def installed_app_ids(libraries: list[Path] | None = None) -> set[str]:
    """Steam app ids with an install manifest in any library on this PC."""
    ids = set()
    for lib in (libraries if libraries is not None else _libraries()):
        try:
            for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
                m = re.fullmatch(r"appmanifest_(\d+)\.acf", acf.name)
                if m:
                    ids.add(m.group(1))
        except OSError:
            continue
    return ids


def _install_dir(lib: Path, app_id: str) -> Path | None:
    acf = lib / "steamapps" / f"appmanifest_{app_id}.acf"
    try:
        text = acf.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = re.search(r'"installdir"\s+"([^"]+)"', text)
    if not m:
        return None
    folder = lib / "steamapps" / "common" / m.group(1)
    return folder if folder.is_dir() else None


def find_game_exe(profile=None, libraries: list[Path] | None = None) -> Path | None:
    """Full path to the game's exe, or None if it isn't installed via Steam."""
    profile = profile or games.DRAGONWILDS
    for lib in (libraries if libraries is not None else _libraries()):
        folder = _install_dir(lib, profile.steam_app_id)
        if not folder:
            continue
        for name in profile.process_names:
            try:
                hits = [p for p in folder.rglob(name) if p.is_file()]
            except OSError:
                continue
            if hits:
                hits.sort(key=lambda p: len(p.parts))   # the top-level exe, not a helper
                log.info("Found %s install: %s", profile.name, hits[0])
                return hits[0]
    return None
