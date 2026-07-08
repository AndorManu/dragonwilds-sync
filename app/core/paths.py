"""Well-known locations and game constants."""

import os
from pathlib import Path

APP_ID = "DragonwildsSync"

# Per-user app data (config, state, logs, safety backups).
APP_DIR = Path(os.environ.get("APPDATA", str(Path.home()))) / APP_ID
CONFIG_PATH = APP_DIR / "config.json"
STATE_PATH = APP_DIR / "state.json"
LOG_DIR = APP_DIR / "logs"
BACKUP_DIR = APP_DIR / "backups"

# Config location used by the original CLI/Tkinter prototype; migrated on first run.
LEGACY_DIR = Path.home() / ".dragonwilds_sync"
LEGACY_CONFIG_PATH = LEGACY_DIR / "config.json"
LEGACY_STATE_PATH = LEGACY_DIR / "state.json"

DEFAULT_SAVE_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "RSDragonwilds" / "Saved" / "SaveGames"
)
GAME_PROCESS_NAME = "RSDragonwilds.exe"
STEAM_APP_ID = "1374490"
MANIFEST_NAME = "version.json"
