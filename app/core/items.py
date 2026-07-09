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
# Every category gets a distinct item silhouette — earlier versions reused skill
# emblems (ores drew the mining pickaxe, food the cooking pot), which read as the
# wrong thing in a bag grid.
CATEGORY_ICON = {
    "Melee Weapons": "cat-sword", "Bows": "cat-bow", "Crossbows": "cat-bow",
    "Arrows": "cat-arrow", "Staves": "cat-staff", "Shields": "cat-shield",
    "Chestplates": "cat-armor", "Helms": "cat-helm", "Leggings": "cat-armor",
    "Capes": "cat-cape", "Rings": "cat-ring", "Amulets": "cat-amulet",
    "Food": "cat-food", "Potions": "cat-potion", "Herbs": "cat-herb",
    "Farming": "cat-seed", "Woodcutting": "cat-log",
    "Tools": "cat-tool", "Ores": "cat-ore", "Bars": "cat-bar",
    "Runes": "cat-rune", "Runecrafting": "cat-rune",
    "Bones": "cat-bone", "Tombs": "cat-tomb", "Basic Item": "gem",
}

# Material tiers. Many items come in a ladder of materials sharing one base name
# ("Bronze Dagger" → "Iron Dagger" → "Steel Dagger" → "Mithril Dagger"). This is
# a single global rank order; only the *relative* order inside a family matters,
# and families are homogeneous (all metals, or all woods), so metal and wood
# ranks can interleave freely. Ties (Copper/Tin, both bronze precursors) are
# siblings — an upgrade skips to the next strictly-higher rank.
MATERIAL_RANK = {
    "Wooden": 0, "Wood": 0, "Leather": 1, "Hardleather": 2, "Studded": 3,
    "Copper": 4, "Tin": 4, "Bronze": 5, "Oak": 5,
    "Iron": 6, "Silver": 7, "Willow": 7, "Steel": 8,
    "Gold": 9, "Maple": 9, "Mithril": 10, "Yew": 11,
    "Adamant": 12, "Adamantite": 12, "Rune": 13, "Runite": 13,
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


# The game splits the flat inventory into visual pouches by category. We
# mirror that so the grimoire reads like the in-game bag.
POUCHES = [
    ("Gear & Tools", ("Melee Weapons", "Bows", "Crossbows", "Staves",
                      "Shields", "Helms", "Chestplates", "Leggings", "Capes",
                      "Rings", "Amulets", "Tools")),
    ("Runes", ("Runes", "Runecrafting")),
    ("Ammo", ("Arrows",)),
    ("Consumables", ("Food", "Potions", "Herbs")),
    ("Materials", ("Ores", "Bars", "Woodcutting", "Farming", "Bones")),
]
_CATEGORY_POUCH = {cat: name for name, cats in POUCHES for cat in cats}


def pouch(item_data: str) -> str:
    return _CATEGORY_POUCH.get(category(item_data), "Materials")


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


def is_stackable(item_data: str) -> bool:
    return max_stack(item_data) > 1


@lru_cache(maxsize=1)
def _tier_index():
    """Build the material-tier families from the catalogue.

    Returns (ladders, of_item):
      ladders  {(category, base): [member, …] sorted by rank}
      of_item  {item_id: (family_key, rank, material)}
    A member is {id, name, material, rank}. Singleton families (nothing to
    upgrade to) are dropped, so membership implies a real ladder.
    """
    fams: dict = {}
    of_item: dict = {}
    for iid, entry in _catalog().items():
        name = entry.get("name") or ""
        if " " not in name:
            continue
        material, base = name.split(" ", 1)
        rank = MATERIAL_RANK.get(material)
        if rank is None or not base.strip():
            continue
        family = (entry.get("category"), base)
        fams.setdefault(family, []).append(
            {"id": iid, "name": name, "material": material, "rank": rank})
        of_item[iid] = (family, rank, material)
    ladders = {}
    for family, members in fams.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda m: m["rank"])
        ladders[family] = members
    of_item = {iid: v for iid, v in of_item.items() if v[0] in ladders}
    return ladders, of_item


def tier_ladder(item_data: str) -> list[dict]:
    """Every material tier of this item's family, low → high (or [] if none)."""
    ladders, of_item = _tier_index()
    info = of_item.get(item_data)
    return ladders.get(info[0], []) if info else []


def tier_position(item_data: str) -> tuple[int, int]:
    """(1-based position, ladder length) of this item, or (0, 0) if untiered."""
    ladder = tier_ladder(item_data)
    for i, m in enumerate(ladder):
        if m["id"] == item_data:
            return i + 1, len(ladder)
    return 0, 0


def tier_neighbor(item_data: str, direction: int) -> dict | None:
    """The next material up (direction>0) or down (<0), skipping equal ranks.

    Returns the member dict {id, name, material, rank} or None at the end.
    """
    ladders, of_item = _tier_index()
    info = of_item.get(item_data)
    if not info:
        return None
    family, rank, _material = info
    members = ladders[family]
    if direction > 0:
        higher = [m for m in members if m["rank"] > rank]
        return higher[0] if higher else None
    lower = [m for m in members if m["rank"] < rank]
    return lower[-1] if lower else None
