"""The item catalogue — names, categories, stack sizes, rarity.

The name/id/category/stack facts are datamined game data (community tools
PEAKEGames/DWCharacterEditor and KevinStillman/dragonwilder); the app draws
its own category icons and never ships the game's icon art. Rarity is a 1-6
tier derived from the game's PowerLevel (with a name-keyword fallback for
non-gear), used only for sorting and colour.
"""

import json
import logging
import sys
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("dwsync.items")

# rank -> (label, colour). Colours match the app's avatar palette family.
RARITY = {
    1: ("Common", "#9AA7B6"),
    2: ("Fine", "#9BCB57"),
    3: ("Uncommon", "#4FC7D4"),
    4: ("Rare", "#5EA2EF"),
    5: ("Epic", "#B78AF7"),
    6: ("Legendary", "#E8A23D"),
}

# Category -> our own icon key (drawn in ui/icons.py). Unmapped -> "gem".
CATEGORY_ICON = {
    "Melee Weapons": "cat-sword", "Bows": "cat-bow", "Crossbows": "cat-bow",
    "Arrows": "cat-arrow", "Staves": "skill-magic", "Shields": "cat-shield",
    "Chestplates": "cat-armor", "Helms": "cat-helm", "Leggings": "cat-armor",
    "Capes": "cat-cape", "Rings": "cat-ring", "Amulets": "cat-amulet",
    "Food": "skill-cooking", "Potions": "cat-potion", "Herbs": "cat-herb",
    "Farming": "skill-farming", "Woodcutting": "skill-woodcutting",
    "Tools": "cat-tool", "Ores": "skill-mining", "Bars": "cat-bar",
    "Runes": "cat-rune", "Runecrafting": "skill-runecrafting",
    "Tombs": "cat-tomb", "Basic Item": "gem",
}


def _asset_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS",
                        Path(__file__).resolve().parent.parent.parent))
    return base / "app" / "assets" / "items.json"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    try:
        payload = json.loads(_asset_path().read_text(encoding="utf-8"))
        return payload.get("items", {})
    except (OSError, json.JSONDecodeError):
        log.warning("Item catalogue missing or unreadable", exc_info=True)
        return {}


def known(item_data: str) -> bool:
    return item_data in _catalog()


def name(item_data: str) -> str:
    entry = _catalog().get(item_data)
    return entry["name"] if entry else "Unknown item"


def info(item_data: str) -> dict | None:
    return _catalog().get(item_data)


def category(item_data: str) -> str:
    entry = _catalog().get(item_data)
    return entry["category"] if entry else "Unknown"


def max_stack(item_data: str) -> int:
    entry = _catalog().get(item_data)
    return int(entry["max"]) if entry else 9999


def rank(item_data: str) -> int:
    entry = _catalog().get(item_data)
    return int(entry["rank"]) if entry else 1


def rarity(item_data: str) -> tuple[str, str]:
    return RARITY.get(rank(item_data), RARITY[1])


def icon_key(item_data: str) -> str:
    return CATEGORY_ICON.get(category(item_data), "gem")


def categories() -> list[str]:
    seen = {}
    for entry in _catalog().values():
        seen[entry["category"]] = seen.get(entry["category"], 0) + 1
    return sorted(seen, key=lambda c: (-seen[c], c))


def search(query: str = "", category_filter: str = "", min_rank: int = 0) -> list[dict]:
    """Catalogue rows matching filters, sorted by rarity desc then name.

    Each row: {id, name, category, max, rank}.
    """
    q = (query or "").strip().lower()
    rows = []
    for item_id, entry in _catalog().items():
        if category_filter and entry["category"] != category_filter:
            continue
        if entry["rank"] < min_rank:
            continue
        if q and q not in entry["name"].lower():
            continue
        rows.append({"id": item_id, **entry})
    rows.sort(key=lambda r: (-r["rank"], r["name"].lower()))
    return rows
