"""Config/state schema v3: a library of games, each with its worlds.

v1 (single world, flat) and v2 (multiple Dragonwilds worlds) migrate
automatically and non-destructively: the old files are kept as
``config.v1.bak`` / ``config.v2.bak``. In v3 every world names its game;
anything from before 2.0 is a Dragonwilds world.

The sync core keeps its v1-shaped flat dict interface; ``effective_cfg``
builds that flat dict for one world. That boundary is what lets every new
feature ship without touching the protocol code.
"""

import logging
import shutil
import uuid

from . import games, paths
from .storage import load_config as _load_raw_config
from .storage import load_state as _load_raw_state
from .storage import save_config, save_state

log = logging.getLogger("dwsync.config")

CONFIG_SCHEMA = 3

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
    "publish_status_page": True,
    "characters_dir": None,        # None -> derived beside the save folder
    "travel_characters": [],       # character file stems that follow you across PCs
    "play_chime": True,
    "discord_app_id": "",
    "active_world": None,
    "worlds": [],
    "library": [],          # game ids in the order the player added them
    "games": {},            # per-game machine settings: {id: {save_dir, exe_path}}
    "last_view": None,      # "library" or a game id - where the app reopens
}

WORLD_DEFAULTS = {
    "id": None,
    "game": games.DEFAULT_GAME,
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


def _to_v3(cfg: dict) -> dict:
    """Fill v3 fields: every world gets a game, the library lists them."""
    for w in cfg.get("worlds", []):
        w.setdefault("game", games.DEFAULT_GAME)
    library = list(cfg.get("library") or [])
    for w in cfg.get("worlds", []):
        if w["game"] not in library:
            library.append(w["game"])
    cfg["library"] = library
    cfg["games"] = dict(cfg.get("games") or {})
    if cfg.get("last_view") is None and library:
        cfg["last_view"] = library[0]
    cfg["schema"] = CONFIG_SCHEMA
    return cfg


def migrate_config(cfg: dict) -> tuple[dict, str | None]:
    """Any older config -> v3. Returns (v3_config, migrated_world_id | None)."""
    if not _is_v1(cfg):
        merged = dict(GLOBAL_DEFAULTS)
        merged.update(cfg)
        return _to_v3(merged), None
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
    return _to_v3(v2), world["id"]


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
        older = cfg.get("schema", 2) < CONFIG_SCHEMA
        if older:
            log.info("Migrating config to v%d (game library)", CONFIG_SCHEMA)
            _backup_file(paths.CONFIG_PATH, suffix=f".v{cfg.get('schema', 2)}.bak")
        cfg, _ = migrate_config(cfg)  # fill any missing defaults
        state = migrate_state(state, None)
        if older:
            save_config(cfg)
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


def world_game(world: dict | None) -> games.GameProfile:
    return games.get((world or {}).get("game"))


def worlds_for_game(cfg: dict, game_id: str) -> list[dict]:
    return [w for w in worlds(cfg) if w.get("game", games.DEFAULT_GAME) == game_id]


def library(cfg: dict) -> list[games.GameProfile]:
    return [games.get(g) for g in (cfg or {}).get("library", []) if g in games.BY_ID]


def add_to_library(cfg: dict, game_id: str):
    lib = cfg.setdefault("library", [])
    if game_id not in lib:
        lib.append(game_id)


def remove_from_library(cfg: dict, game_id: str):
    """Only allowed once the game has no worlds left."""
    if worlds_for_game(cfg, game_id):
        raise ValueError("game still has worlds")
    cfg["library"] = [g for g in cfg.get("library", []) if g != game_id]
    cfg.get("games", {}).pop(game_id, None)
    if cfg.get("last_view") == game_id:
        cfg["last_view"] = "library"


def game_settings(cfg: dict, game_id: str) -> dict:
    return cfg.setdefault("games", {}).setdefault(game_id, {})


def game_save_dir(cfg: dict, game_id: str) -> str:
    """The save folder for a game on this PC: the player's choice, else the
    detected default, else where it normally lives (for display).

    Dragonwilds keeps using the v1 ``local_save_dir`` key so the
    Dragonwilds-only extras (characters) keep finding it.
    """
    if game_id == games.DRAGONWILDS.id:
        return cfg.get("local_save_dir") or str(paths.DEFAULT_SAVE_DIR)
    chosen = ((cfg.get("games") or {}).get(game_id) or {}).get("save_dir")
    if chosen:
        return chosen
    profile = games.get(game_id)
    found = games.default_save_dir(profile)
    return str(found or games.fallback_save_dir(profile))


def set_game_save_dir(cfg: dict, game_id: str, folder: str):
    if game_id == games.DRAGONWILDS.id:
        cfg["local_save_dir"] = folder
    else:
        game_settings(cfg, game_id)["save_dir"] = folder


def game_exe_path(cfg: dict, game_id: str) -> str | None:
    if game_id == games.DRAGONWILDS.id:
        return cfg.get("exe_path")
    return ((cfg.get("games") or {}).get(game_id) or {}).get("exe_path")


def effective_cfg(cfg: dict, world: dict) -> dict:
    """The flat, v1-shaped dict the sync core was validated against.

    WorldSync adds a few keys the core reads with .get(): the world's file
    patterns, whether to mirror deletions, and the game id (stamped on the
    manifest and checked on pull). Dragonwilds worlds carry patterns=None,
    which is the exact v1 behaviour.
    """
    profile = world_game(world)
    app_id = profile.steam_app_id
    if profile.id == games.DRAGONWILDS.id:
        app_id = cfg.get("steam_app_id") or app_id
    return {
        "player_name": cfg.get("player_name", ""),
        "local_save_dir": game_save_dir(cfg, profile.id),
        "world_name": world.get("world_name", ""),
        "sync_dir": world.get("sync_dir", ""),
        "exe_path": game_exe_path(cfg, profile.id),
        "steam_app_id": app_id,
        "game": profile.id,
        "patterns": list(profile.patterns) if profile.patterns is not None else None,
        "mirror": profile.mirror,
        "process_names": list(profile.process_names),
    }


def world_state(state: dict, world_id: str) -> dict:
    """Mutable per-world state slice; created on first access.

    The sync core mutates this dict in place; persisting the parent `state`
    afterwards saves it - same contract as v1.
    """
    slot = state.setdefault("worlds", {}).setdefault(world_id, {})
    slot.setdefault("last_applied_version", 0)
    slot.setdefault("last_hash", None)
    return slot


def backup_root_for(world_id: str):
    return paths.BACKUP_DIR / world_id
