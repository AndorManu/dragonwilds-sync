"""Config/state persistence with atomic writes and prototype migration."""

import json
import logging
import os
from pathlib import Path

from . import paths

log = logging.getLogger("dwsync.storage")


def read_json(path: Path, default=None):
    """Read JSON, returning `default` on absence or corruption (corruption is logged)."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Could not read %s: %s", path, e)
    return default


def write_json(path: Path, data):
    """Write JSON atomically (temp file + replace) so readers never see a half-write."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)


def load_config():
    cfg = read_json(paths.CONFIG_PATH)
    if cfg is None and paths.LEGACY_CONFIG_PATH.exists():
        cfg = read_json(paths.LEGACY_CONFIG_PATH)
        if cfg:
            log.info("Migrating config from prototype location %s", paths.LEGACY_DIR)
            write_json(paths.CONFIG_PATH, cfg)
            legacy_state = read_json(paths.LEGACY_STATE_PATH)
            if legacy_state and not paths.STATE_PATH.exists():
                write_json(paths.STATE_PATH, legacy_state)
    return cfg


def save_config(cfg):
    write_json(paths.CONFIG_PATH, cfg)


def load_state():
    return read_json(paths.STATE_PATH, {"last_applied_version": 0, "last_hash": None})


def save_state(state):
    write_json(paths.STATE_PATH, state)
