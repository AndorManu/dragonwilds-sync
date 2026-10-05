"""Well-known locations. Per-game paths live in games.py."""

import os
from pathlib import Path

APP_ID = "WorldSync"

# Per-user app data (config, state, logs, safety backups).
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_ID
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOG_DIR = APP_DIR / "logs"
BACKUP_DIR = APP_DIR / "backups"

# Before 2.0 the app was "Dragonwilds Sync" and lived here; copied over on first run.
LEGACY_APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / "DragonwildsSync"

# Config location used by the original CLI/Tkinter prototype; migrated on first run.
LEGACY_DIR = Path.home() / ".dragonwilds_sync"
LEGACY_CONFIG_PATH = LEGACY_DIR / "config.json"
LEGACY_STATE_PATH = LEGACY_DIR / "state.json"

# Dragonwilds defaults, still used by the Dragonwilds-only extras.
DEFAULT_SAVE_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "RSDragonwilds" / "Saved" / "SaveGames"
)
GAME_PROCESS_NAME = "RSDragonwilds.exe"
STEAM_APP_ID = "1374490"
MANIFEST_NAME = "version.json"
