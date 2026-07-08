"""Finding the game install via the Steam registry + library folders."""

import logging
import re
from pathlib import Path

from . import paths

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


def find_game_exe() -> Path | None:
    """Full path to RSDragonwilds.exe, or None if not found."""
    root = _steam_root()
    if not root:
        return None
    for lib in _library_folders(root):
        common = lib / "steamapps" / "common"
        try:
            candidates = list(common.glob("*Dragonwilds*/" + paths.GAME_PROCESS_NAME))
        except OSError:
            continue
        for c in candidates:
            if c.is_file():
                log.info("Found game install: %s", c)
                return c
    return None
