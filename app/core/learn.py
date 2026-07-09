"""Browseable catalogue for the Learn picker: pick specific spells, recipes,
or buildings to unlock. Recipes resolve to their output item so they carry a
recognisable category glyph and rarity colour.

Facts only (datamined ids/names); icons are drawn in-house.
"""

import json
import logging
from functools import lru_cache
from pathlib import Path

from . import items

log = logging.getLogger("dwsync.learn")

SPELL_COLOR = "#B78AF7"      # arcane violet
BUILDING_COLOR = "#E8A23D"   # ember gold

KINDS = ("spells", "recipes", "buildings")


def _asset_path() -> Path:
    return items._asset_path().parent / "learnables.json"


@lru_cache(maxsize=1)
def _catalog() -> dict:
    try:
        return json.loads(_asset_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log.warning("Learnables catalogue missing", exc_info=True)
        return {"spells": [], "recipes": [], "buildings": []}


def total(kind: str) -> int:
    return len(_catalog().get(kind, []))


def recipe_categories() -> list[str]:
    seen = {}
    for r in _catalog().get("recipes", []):
        seen[r["cat"]] = seen.get(r["cat"], 0) + 1
    return sorted(seen, key=lambda c: (-seen[c], c))


def _row(kind: str, entry: dict, owned: set) -> dict:
    if kind == "recipes":
        rank = int(entry.get("rank", 1))
        cat = entry.get("cat", "Basic Item")
        label, color = items.RARITY.get(rank, items.RARITY[1])
        icon = items.CATEGORY_ICON.get(cat, "gem")
        sub = f"{label} · {cat}"
        if entry.get("station"):
            sub += f" · {entry['station']}"
    elif kind == "spells":
        rank, color, icon = 0, SPELL_COLOR, "skill-magic"
        sub = "Spell"
    else:  # buildings
        rank, color, icon = 0, BUILDING_COLOR, "skill-construction"
        sub = "Building"
    return {"id": entry["id"], "name": entry["name"], "icon": icon,
            "color": color, "rank": rank, "sub": sub,
            "owned": entry["id"] in owned}


def search(kind: str, query: str = "", category: str = "", min_rank: int = 0,
           owned: set | None = None) -> list[dict]:
    owned = owned or set()
    q = (query or "").strip().lower()
    rows = []
    for entry in _catalog().get(kind, []):
        if q and q not in entry["name"].lower():
            continue
        if kind == "recipes":
            if category and entry.get("cat") != category:
                continue
            if int(entry.get("rank", 1)) < min_rank:
                continue
        rows.append(_row(kind, entry, owned))
    if kind == "recipes":
        rows.sort(key=lambda r: (r["owned"], -r["rank"], r["name"].lower()))
    else:
        rows.sort(key=lambda r: (r["owned"], r["name"].lower()))
    return rows
