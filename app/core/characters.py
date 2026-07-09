"""Reading — and carefully editing — Dragonwilds character files.

Characters live beside the world saves (``Saved\\SaveCharacters``) as
pretty-printed JSON with a ``.backup`` twin, mirroring the world pattern.
Verified structure (game Version 75):

- ``meta_data``: char_guid, char_name, worlds_playtime (world-guid → unix
  timestamp of last play), char_type
- ``Customization.CustomizationData``: appearance rows (BodyType, SkinTone,
  HairPreset, HairColor, FacialHairPreset, EyeColor, …)
- ``GameProgress.Character``: vitals (Health/Stamina CurrentValue,
  Sustenance/Hydration/Endurance values), Playtime_wall seconds
- ``GameProgress.Inventory``: slots with plain-integer Count / Durability
- ``GameProgress.Skills.Skills``: 11 ``{Id, Xp}`` pairs, Xp a bare integer;
  the Ids are opaque but identical across characters
- ``Backup``: unknown 32-bit value, changes every save. Tested: NOT a
  CRC32/Adler32 of any obvious content. We never touch it.

Editing philosophy: modify only the exact values asked for, leave every
other field (including ``Backup``) untouched, always checkpoint first,
always verify the result re-parses to exactly the intended structure before
replacing the file. The ``.backup`` twin is never modified — it's the game's
own second safety net and doubles as ours.
"""

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from . import backups
from .storage import read_json, write_json

log = logging.getLogger("dwsync.characters")

DEFAULT_CHARACTERS_DIR = (
    Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    / "RSDragonwilds" / "Saved" / "SaveCharacters"
)

# The canonical skill-GUID -> name mapping, cracked 2026-07-08 by matching
# in-game skill-panel XP values against the file, all 11 exact and unique.
# The Ids are identical across characters, so this holds game-wide (until a
# game update adds skills — the identify ritual covers that day).
DEFAULT_SKILL_LABELS = {
    "4pefO9k1lUqfA6mvHNi1SA": "Attack",
    "0hreSMRVXUihq9qjDO2CFA": "Magic",
    "heq7u88Q2UuLXFqLGTVwQw": "Ranged",
    "jqX0Gh6QI0GFFPCDFK_CJQ": "Mining",
    "4zYUGF5u_0KbMLkWJmmBbQ": "Woodcutting",
    "Wf3i7Ha-B06DH719j1vtBw": "Artisan",
    "waK-8EyQFQ2xEjCGYmuTRQ": "Construction",
    "Tn7t6DQyX0-Q0cM5K7B90A": "Cooking",
    "PyUi-0LU_riFY46AnnFiWg": "Farming",
    "NOqC-z-2ckqi0El22qMFlw": "Runecrafting",
    "vwY5IkQJJDwb2PKEfoc8MQ": "Fishing",
}

# Candidate names for the identify ritual (future/unknown skills).
SKILL_NAME_CHOICES = sorted(set(DEFAULT_SKILL_LABELS.values())) + [
    "Firemaking", "Smithing", "Defence", "Agility", "Slayer",
]


def skill_label(skill_id: str, index: int = 0, user_labels: dict | None = None) -> str:
    """User's own label > the canonical map > a numbered fallback."""
    if user_labels and user_labels.get(skill_id):
        return user_labels[skill_id]
    if skill_id in DEFAULT_SKILL_LABELS:
        return DEFAULT_SKILL_LABELS[skill_id]
    return f"Skill {index + 1}"


@dataclass
class CharacterInfo:
    path: Path
    name: str = "?"
    guid: str = ""
    playtime_s: float = 0.0
    last_played: datetime | None = None
    health: float | None = None
    stamina: float | None = None
    skills: list = field(default_factory=list)       # [{"Id","Xp"}]
    total_xp: int = 0
    inventory_slots: int = 0
    appearance: dict = field(default_factory=dict)   # {slot: rowName}
    save_count: int = 0


def characters_dir(cfg: dict) -> Path:
    """Configured folder, else derived from the save folder, else default."""
    configured = (cfg or {}).get("characters_dir")
    if configured:
        return Path(configured)
    save_dir = (cfg or {}).get("local_save_dir")
    if save_dir:
        sibling = Path(save_dir).parent / "SaveCharacters"
        if sibling.exists():
            return sibling
    return DEFAULT_CHARACTERS_DIR


def character_files(folder) -> list[Path]:
    folder = Path(folder)
    if not folder.exists():
        return []
    return sorted(p for p in folder.glob("*.json") if p.is_file())


def _appearance_rows(data: dict) -> dict:
    rows = {}
    custom = (data.get("Customization") or {}).get("CustomizationData") or {}
    for slot, entry in custom.items():
        if isinstance(entry, dict) and entry.get("rowName"):
            rows[slot] = entry["rowName"]
    return rows


def parse_character(path) -> CharacterInfo | None:
    path = Path(path)
    data = read_json(path)
    if not isinstance(data, dict):
        return None
    info = CharacterInfo(path=path)
    meta = data.get("meta_data") or {}
    info.name = meta.get("char_name") or path.stem
    info.guid = meta.get("char_guid", "")
    info.save_count = data.get("SaveCount", 0)

    stamps = [v for v in (meta.get("worlds_playtime") or {}).values()
              if isinstance(v, (int, float)) and v > 1_000_000_000]
    if stamps:
        try:
            info.last_played = datetime.fromtimestamp(max(stamps), tz=timezone.utc)
        except (OSError, OverflowError, ValueError):
            pass

    progress = data.get("GameProgress") or {}
    char = progress.get("Character") or {}
    info.playtime_s = float(char.get("Playtime_wall") or 0.0)
    health = char.get("Health") or {}
    stamina = char.get("Stamina") or {}
    info.health = health.get("CurrentValue")
    info.stamina = stamina.get("CurrentValue")

    skills = ((progress.get("Skills") or {}).get("Skills")) or []
    info.skills = [s for s in skills if isinstance(s, dict) and "Id" in s]
    info.total_xp = sum(int(s.get("Xp") or 0) for s in info.skills)

    inventory = progress.get("Inventory") or {}
    info.inventory_slots = sum(1 for k, v in inventory.items()
                               if isinstance(v, dict) and k != "MaxSlotIndex")
    info.appearance = _appearance_rows(data)
    return info


def list_characters(folder) -> list[CharacterInfo]:
    infos = []
    for p in character_files(folder):
        info = parse_character(p)
        if info:
            infos.append(info)
    infos.sort(key=lambda i: i.last_played or datetime.min.replace(tzinfo=timezone.utc),
               reverse=True)
    return infos


def portrait_descriptor(info: CharacterInfo) -> str:
    """Compact appearance string safe to embed in the shared manifest."""
    rows = info.appearance
    parts = [
        rows.get("BodyType", ""), rows.get("SkinTone", ""),
        rows.get("HairPreset", ""), rows.get("HairColor", ""),
        rows.get("FacialHairPreset", ""), rows.get("EyeColor", ""),
    ]
    return "|".join(p[:24] for p in parts)


# ---------------------------------------------------------------------------
# knowledge — the Scroll of Knowledge
# ---------------------------------------------------------------------------

# Category -> path inside the character JSON. All are lists of opaque ids
# except the map bitmap (an int we OR together). Union-merging these between
# characters never invents ids, so it can't create anything the game doesn't
# already recognise.
KNOWLEDGE_PATHS = {
    "recipes": ("GameProgress", "Progress", "RecipesUnlocked"),
    "recipes_new": ("GameProgress", "Progress", "RecipesNew"),
    "buildings": ("GameProgress", "Progress", "BuildingsUnlocked"),
    "building_pieces_new": ("GameProgress", "Progress", "BuildingPiecesNew"),
    "spells": ("GameProgress", "Progress", "SpellsUnlocked"),
    "spells_new": ("GameProgress", "Progress", "SpellsNew"),
    "shrines": ("GameProgress", "Progress", "ShrinesUnlocked"),
    "journal": ("GameProgress", "Journal", "UnlockedEntries"),
    "mounts": ("GameProgress", "Character", "Mount", "MountsUnlockedList"),
    "landmarks": ("GameProgress", "RevealedLandmarks", "RevealedLandmarkNames"),
}
MAP_BITMAP_PATH = ("GameProgress", "RevealedFog", "RevealedRegionsBitmap")

# What the UI shows for each category (display name, headline categories first)
KNOWLEDGE_DISPLAY = [
    ("recipes", "Recipes"), ("buildings", "Buildings"), ("spells", "Spells"),
    ("journal", "Journal"), ("shrines", "Shrines"), ("mounts", "Mounts"),
    ("landmarks", "Landmarks"),
]

SCROLL_VERSION = 1


def _get_path(data: dict, path: tuple):
    node = data
    for key in path:
        if not isinstance(node, dict) or key not in node:
            return None
        node = node[key]
    return node


def extract_knowledge(data: dict) -> dict:
    """Everything a character has unlocked, as a portable scroll payload."""
    knowledge = {}
    for name, path in KNOWLEDGE_PATHS.items():
        value = _get_path(data, path)
        if isinstance(value, list):
            knowledge[name] = list(value)
    bitmap = _get_path(data, MAP_BITMAP_PATH)
    if isinstance(bitmap, int):
        knowledge["map_bitmap"] = bitmap
    return knowledge


def diff_knowledge(data: dict, scroll: dict) -> dict:
    """{category: how much is new} — what absorbing the scroll would add."""
    gains = {}
    for name, path in KNOWLEDGE_PATHS.items():
        incoming = scroll.get(name) or []
        existing = _get_path(data, path)
        if not isinstance(existing, list):
            continue
        have = set(map(str, existing))
        new = [x for x in incoming if str(x) not in have]
        if new:
            gains[name] = len(new)
    incoming_bits = scroll.get("map_bitmap")
    existing_bits = _get_path(data, MAP_BITMAP_PATH)
    if isinstance(incoming_bits, int) and isinstance(existing_bits, int):
        added = (existing_bits | incoming_bits) & ~existing_bits
        if added:
            gains["map_regions"] = bin(added).count("1")
    return gains


def absorb_knowledge(path, scroll: dict, backup_root) -> dict:
    """Union-merge a scroll into a character file. Returns the gains applied.

    Same safety contract as apply_edits: checkpoint first, only the listed
    knowledge fields change (append-only unions / bitmap OR), atomic write.
    """
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    gains = diff_knowledge(data, scroll)
    if not gains:
        return {}

    stamp = datetime.now().strftime("%H:%M")
    backups.create_checkpoint(path.parent, path.stem,
                              f"Before the scroll ({stamp})", backup_root)

    for name, kpath in KNOWLEDGE_PATHS.items():
        incoming = scroll.get(name) or []
        existing = _get_path(data, kpath)
        if not isinstance(existing, list) or not incoming:
            continue
        have = set(map(str, existing))
        existing.extend(x for x in incoming if str(x) not in have)
    incoming_bits = scroll.get("map_bitmap")
    existing_bits = _get_path(data, MAP_BITMAP_PATH)
    if isinstance(incoming_bits, int) and isinstance(existing_bits, int):
        parent = _get_path(data, MAP_BITMAP_PATH[:-1])
        parent[MAP_BITMAP_PATH[-1]] = existing_bits | incoming_bits

    _write_character(path, data)
    log.info("Scroll absorbed into %s: %s", path.name, gains)
    return gains


def knowledge_counts(info_or_data) -> dict:
    """{category: count} for the UI stat cards (map as region count)."""
    data = info_or_data
    counts = {}
    for name, path in KNOWLEDGE_PATHS.items():
        value = _get_path(data, path)
        if isinstance(value, list):
            counts[name] = len(value)
    bitmap = _get_path(data, MAP_BITMAP_PATH)
    if isinstance(bitmap, int):
        counts["map_regions"] = bin(max(0, bitmap)).count("1")
    return counts


def write_scroll(char_path, dest_path, author: str) -> Path:
    data = json.loads(Path(char_path).read_text(encoding="utf-8"))
    info = parse_character(char_path)
    payload = {
        "scroll_version": SCROLL_VERSION,
        "author": author,
        "character": info.name if info else Path(char_path).stem,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "knowledge": extract_knowledge(data),
    }
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, payload)
    return dest


def read_scroll(path) -> dict | None:
    payload = read_json(Path(path))
    if not isinstance(payload, dict) or "knowledge" not in payload:
        return None
    return payload


# ---------------------------------------------------------------------------
# the bag — inventory + Gift Across the Void
# ---------------------------------------------------------------------------

@dataclass
class InventorySlot:
    index: int
    item_data: str
    guid: str
    count: int | None = None
    durability: int | None = None


def list_inventory(data: dict) -> tuple[list[InventorySlot], int]:
    """(occupied slots sorted by index, MaxSlotIndex)."""
    inventory = _get_path(data, ("GameProgress", "Inventory")) or {}
    slots = []
    max_index = int(inventory.get("MaxSlotIndex", -1))
    for key, value in inventory.items():
        if key == "MaxSlotIndex" or not isinstance(value, dict):
            continue
        try:
            index = int(key)
        except ValueError:
            continue
        slots.append(InventorySlot(
            index=index,
            item_data=str(value.get("ItemData", "")),
            guid=str(value.get("GUID", "")),
            count=value.get("Count"),
            durability=value.get("Durability"),
        ))
    slots.sort(key=lambda s: s.index)
    return slots, max_index


def first_free_slot(data: dict) -> int | None:
    slots, max_index = list_inventory(data)
    used = {s.index for s in slots}
    for i in range(max(max_index + 1, 1)):
        if i not in used:
            return i
    return None


def new_item_guid() -> str:
    """Fresh id in the game's observed format: 16 random bytes, base64url."""
    import base64
    import os as _os
    return base64.urlsafe_b64encode(_os.urandom(16)).rstrip(b"=").decode("ascii")


def export_offering(char_path, dest_path, author: str) -> Path:
    """Write this character's inventory as a gift catalogue for friends."""
    data = json.loads(Path(char_path).read_text(encoding="utf-8"))
    slots, _ = list_inventory(data)
    items = []
    for s in slots:
        entry = {"ItemData": s.item_data, "slot": s.index}
        if s.count is not None:
            entry["Count"] = int(s.count)
        if s.durability is not None:
            entry["Durability"] = int(s.durability)
        items.append(entry)
    payload = {
        "gift_version": SCROLL_VERSION,
        "author": author,
        "character": Path(char_path).stem,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "items": items,
    }
    dest = Path(dest_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    write_json(dest, payload)
    return dest


def read_offering(path) -> dict | None:
    payload = read_json(Path(path))
    if not isinstance(payload, dict) or "items" not in payload:
        return None
    return payload


def receive_gift(char_path, item_entry: dict, backup_root) -> int | None:
    """Copy one offered item entry into the first free slot. Experimental:
    checkpoint-first, fresh GUID, respects the bag's MaxSlotIndex.

    Returns the slot index used, or None if the bag is full / entry invalid.
    """
    path = Path(char_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    item_data = str(item_entry.get("ItemData") or "")
    if not item_data:
        return None
    free = first_free_slot(data)
    if free is None:
        return None

    stamp = datetime.now().strftime("%H:%M")
    backups.create_checkpoint(path.parent, path.stem,
                              f"Before the gift ({stamp})", backup_root)

    slot = {"GUID": new_item_guid(), "ItemData": item_data}
    if item_entry.get("Count") is not None:
        slot["Count"] = max(1, int(item_entry["Count"]))
    if item_entry.get("Durability") is not None:
        slot["Durability"] = max(1, int(item_entry["Durability"]))
    inventory = _get_path(data, ("GameProgress", "Inventory"))
    inventory[str(free)] = slot

    _write_character(path, data)
    log.info("Gift placed in slot %d of %s", free, path.name)
    return free


def _write_character(path: Path, data: dict):
    """Serialize like the game (tabs, raw unicode), verify, atomic replace."""
    new_text = json.dumps(data, indent="\t", ensure_ascii=False)
    if json.loads(new_text) != data:
        raise ValueError("round-trip verification failed; file left untouched")
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(new_text, encoding="utf-8")
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# editing — The Dragon's Bargain
# ---------------------------------------------------------------------------

@dataclass
class EditPlan:
    """What the grimoire wants changed. Only these values are touched."""
    skill_xp: dict = field(default_factory=dict)        # skill Id -> new Xp int
    heal_vitals: bool = False                           # health/stamina to max-ish
    repair_all: bool = False                            # every Durability -> max
    item_counts: dict = field(default_factory=dict)     # slot key -> new Count
    item_repairs: set = field(default_factory=set)      # slot keys to repair

    def empty(self) -> bool:
        return not (self.skill_xp or self.heal_vitals or self.repair_all
                    or self.item_counts or self.item_repairs)


REPAIR_VALUE = 9999
HEAL_VALUE = 100000.0   # game clamps to the character's real maximum on load


def apply_edits(path, plan: EditPlan, backup_root) -> list[str]:
    """Apply an EditPlan to a character file. Returns a list of change notes.

    Safety: checkpoint first; modify only planned values in the parsed dict;
    re-serialize; verify the result parses back to the modified dict; atomic
    replace. The .backup twin and the Backup field are never touched.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    changes: list[str] = []

    # 1. checkpoint the character (both json and its .backup twin)
    stamp = datetime.now().strftime("%H:%M")
    backups.create_checkpoint(path.parent, path.stem,
                              f"Before the bargain ({stamp})", backup_root)

    progress = data.get("GameProgress") or {}

    if plan.skill_xp:
        skills = ((progress.get("Skills") or {}).get("Skills")) or []
        by_id = {s.get("Id"): s for s in skills if isinstance(s, dict)}
        for skill_id, new_xp in plan.skill_xp.items():
            entry = by_id.get(skill_id)
            if entry is None:
                continue
            old = entry.get("Xp")
            new_xp = max(0, int(new_xp))
            if old != new_xp:
                entry["Xp"] = new_xp
                changes.append(f"skill {skill_id[:8]}…: {old} → {new_xp} xp")

    if plan.heal_vitals:
        char = progress.get("Character") or {}
        for key in ("Health", "Stamina"):
            vital = char.get(key)
            if isinstance(vital, dict) and "CurrentValue" in vital:
                vital["CurrentValue"] = HEAL_VALUE
        for key, sub in (("Sustenance", "SustenanceValue"),
                         ("Hydration", "HydrationValue"),
                         ("Endurance", "EnduranceValue")):
            vital = char.get(key)
            if isinstance(vital, dict) and sub in vital:
                vital[sub] = 100.0
        changes.append("vitals restored")

    inventory = progress.get("Inventory") or {}
    if plan.repair_all:
        repaired = 0
        for key, slot in inventory.items():
            if isinstance(slot, dict) and "Durability" in slot:
                slot["Durability"] = REPAIR_VALUE
                repaired += 1
        loadout = progress.get("Loadout") or {}
        for key, slot in loadout.items():
            if isinstance(slot, dict) and "Durability" in slot:
                slot["Durability"] = REPAIR_VALUE
                repaired += 1
        if repaired:
            changes.append(f"{repaired} items repaired")

    for slot_key, new_count in (plan.item_counts or {}).items():
        slot = inventory.get(str(slot_key))
        if isinstance(slot, dict) and "Count" in slot:
            old = slot.get("Count")
            new_count = max(1, int(new_count))
            if old != new_count:
                slot["Count"] = new_count
                changes.append(f"slot {slot_key}: count {old} → {new_count}")

    for slot_key in (plan.item_repairs or ()):
        slot = inventory.get(str(slot_key))
        if isinstance(slot, dict) and "Durability" in slot:
            slot["Durability"] = REPAIR_VALUE
            changes.append(f"slot {slot_key}: repaired")

    if not changes:
        return []

    # 2 + 3. serialize like the game, verify the round trip, atomic replace
    _write_character(path, data)
    log.info("Dragon's bargain applied to %s: %s", path.name, "; ".join(changes))
    return changes


# ---------------------------------------------------------------------------
# skill labelling — the identify ritual
# ---------------------------------------------------------------------------

def load_skill_labels(app_dir) -> dict:
    return read_json(Path(app_dir) / "skill_labels.json", {}) or {}


def save_skill_labels(app_dir, labels: dict):
    write_json(Path(app_dir) / "skill_labels.json", labels)


def snapshot_skills(path) -> dict:
    """{skill Id -> Xp} right now, for diffing after a play session."""
    info = parse_character(path)
    return {s["Id"]: int(s.get("Xp") or 0) for s in (info.skills if info else [])}


def diff_skills(before: dict, after: dict) -> list[tuple[str, int]]:
    """Skills that gained XP, biggest gain first."""
    gains = []
    for skill_id, xp in after.items():
        gained = xp - before.get(skill_id, 0)
        if gained > 0:
            gains.append((skill_id, gained))
    gains.sort(key=lambda t: -t[1])
    return gains
