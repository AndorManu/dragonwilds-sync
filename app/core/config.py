"""Config/state schema v2: multiple worlds, global player + machine settings.

v1 (single world, flat) is migrated automatically and non-destructively:
the old files are kept as ``config.v1.bak`` / ``state.v1.bak``.

The sync core keeps its v1-shaped flat dict interface; ``effective_cfg``
builds that flat dict for one world. That boundary is what lets every new
feature ship without touching the protocol code.
"""

import logging
import shutil
import uuid

from . import paths
from .storage import load_config as _load_raw_config
from .storage import load_state as _load_raw_state
from .storage import save_config, save_state

log = logging.getLogger("dwsync.config")

CONFIG_SCHEMA = 2

GLOBAL_DEFAULTS = {
    "schema": CONFIG_SCHEMA,
    "player_name": "",
    "player_emoji": "",
    "player_color": "",
    "local_save_dir": str(paths.DEFAULT_SAVE_DIR),
    "exe_path": None,
    "steam_app_id": paths.STEAM_APP_ID,
    "close_to_tray": True,
    "launch_on_startup": False,
    "active_world": None,
    "worlds": [],
}

WORLD_DEFAULTS = {
    "id": None,
    "world_name": "",
    "sync_dir": "",
    "share_link": None,
    "webhook_url": None,
}


def new_world_id() -> str:
    return "w_" + uuid.uuid4().hex[:10]


def make_world(world_name: str, sync_dir: str, **extra) -> dict:
    world = dict(WORLD_DEFAULTS)
    world.update({"id": new_world_id(), "world_name": world_name,
                  "sync_dir": sync_dir})
    world.update(extra)
    return world


def _is_v1(cfg: dict) -> bool:
    return "worlds" not in cfg and "world_name" in cfg


def _backup_file(path, suffix=".v1.bak"):
    try:
        if path.exists():
            shutil.copy2(path, path.with_name(path.name.replace(".json", "") + suffix))
    except OSError:
        log.warning("Could not write migration backup for %s", path)


def migrate_config(cfg: dict) -> tuple[dict, str | None]:
    """v1 flat config -> v2. Returns (v2_config, migrated_world_id | None)."""
    if not _is_v1(cfg):
        merged = dict(GLOBAL_DEFAULTS)
        merged.update(cfg)
        return merged, None
    world = make_world(cfg.get("world_name", ""), cfg.get("sync_dir", ""))
    v2 = dict(GLOBAL_DEFAULTS)
    v2.update({
        "player_name": cfg.get("player_name", ""),
        "local_save_dir": cfg.get("local_save_dir", str(paths.DEFAULT_SAVE_DIR)),
        "exe_path": cfg.get("exe_path"),
        "steam_app_id": cfg.get("steam_app_id", paths.STEAM_APP_ID),
        "active_world": world["id"],
        "worlds": [world],
    })
    return v2, world["id"]


def migrate_state(state: dict, migrated_world_id: str | None) -> dict:
    """v1 flat state -> v2 keyed by world id."""
    if "worlds" in state:
        return state
    v2 = {"schema": CONFIG_SCHEMA, "worlds": {}}
    if migrated_world_id and ("last_applied_version" in state or "last_hash" in state):
        v2["worlds"][migrated_world_id] = {
            "last_applied_version": state.get("last_applied_version", 0),
            "last_hash": state.get("last_hash"),
        }
    return v2


def load() -> tuple[dict | None, dict]:
    """Load (config, state), migrating v1 -> v2 on disk if needed."""
    cfg = _load_raw_config()
    state = _load_raw_state()
    if cfg is None:
        return None, {"schema": CONFIG_SCHEMA, "worlds": {}}
    if _is_v1(cfg):
        log.info("Migrating v1 single-world config to v2")
        _backup_file(paths.CONFIG_PATH)
        _backup_file(paths.STATE_PATH)
        cfg, wid = migrate_config(cfg)
        state = migrate_state(state, wid)
        save_config(cfg)
        save_state(state)
    else:
        cfg, _ = migrate_config(cfg)  # fill any missing v2 defaults
        state = migrate_state(state, None)
    return cfg, state


# -- accessors -----------------------------------------------------------------

def worlds(cfg: dict) -> list[dict]:
    return cfg.get("worlds", [])


def world_by_id(cfg: dict, world_id: str) -> dict | None:
    for w in worlds(cfg):
        if w["id"] == world_id:
            return w
    return None


def active_world(cfg: dict) -> dict | None:
    w = world_by_id(cfg, cfg.get("active_world") or "")
    if w is None and worlds(cfg):
        w = worlds(cfg)[0]
    return w


def effective_cfg(cfg: dict, world: dict) -> dict:
    """The flat, v1-shaped dict the sync core was validated against."""
    return {
        "player_name": cfg.get("player_name", ""),
        "local_save_dir": cfg.get("local_save_dir", ""),
        "world_name": world.get("world_name", ""),
        "sync_dir": world.get("sync_dir", ""),
        "exe_path": cfg.get("exe_path"),
        "steam_app_id": cfg.get("steam_app_id", paths.STEAM_APP_ID),
    }


def world_state(state: dict, world_id: str) -> dict:
    """Mutable per-world state slice; created on first access.

    The sync core mutates this dict in place; persisting the parent `state`
    afterwards saves it — same contract as v1.
    """
    slot = state.setdefault("worlds", {}).setdefault(world_id, {})
    slot.setdefault("last_applied_version", 0)
    slot.setdefault("last_hash", None)
    return slot


def backup_root_for(world_id: str):
    return paths.BACKUP_DIR / world_id
